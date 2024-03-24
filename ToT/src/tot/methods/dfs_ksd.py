import itertools
import numpy as np
from functools import partial
from tot.models import gpt
import tot.record_functions as record
import tot.tasks.tree_graph as tree_graph
import tot.tasks.draw as draw
import re

index = 0 # idx

def get_value(task, x, y, n_evaluate_sample, cache_value=True):
    value_prompt = task.value_prompt_wrap(x, y)
    # record.Record_txt(record.record_file_name, '\nvalue prompt: ' + value_prompt + '\n\n', idx = index)
    if 'wrong answer' in y:
        return 0
    if cache_value and value_prompt in task.value_cache:
        return task.value_cache[value_prompt]
    value_outputs = gpt(value_prompt, n=n_evaluate_sample, stop=None, idx = index)
    value = task.value_outputs_unwrap(x, y, value_outputs)
    if cache_value:
        task.value_cache[value_prompt] = value
    return value

def get_values(task, x, ys, n_evaluate_sample, cache_value=True):
    values = []
    local_value_cache = {}
    for y in ys:  # each partial output
        if y in local_value_cache:  # avoid duplicate candidates
            value = 0
        else:    
            value = get_value(task, x, y, n_evaluate_sample, cache_value=cache_value)
            local_value_cache[y] = value
        values.append(value)
    return values

def get_proposals(task, x, y, k):
    global index, gpt
    propose_prompt = task.propose_prompt_wrap(x, y, k)
    record.Record_txt(record.debug_file_name, '\npropose prompt: ' + propose_prompt + '\n\n', idx = index)
    
    # Final Generator use Gpt-4
    if 'Answer' in propose_prompt:
        gpt = partial(gpt, model='gpt-4')
    proposals = gpt(propose_prompt, n=1, stop=None, idx = index)[0].split('\n')
    # add left
    for i in range(len(proposals)):
        if 'answer' in proposals[i].lower():
            continue
        # record.Record_txt(record.record_file_name, '\nget current numbers: ' + get_current_numbers(y if y else x) + '\n\n', idx = index)
        proposals[i] = add_left(proposals[i], get_current_numbers(y if y else x))
    return [y + _ + '\n' for _ in proposals]

def add_left(response, input_string):
    pattern = r"(-?[0-9\.]+)[\s]*([\+\-\*\/])[\s]*(-?[0-9\.]+)[\s]*=[\s]*(-?[0-9\.]+)[\s]*"
    match = re.match(pattern, response)
    if match:
        print(match.group(1), match.group(3), match.group(4))
        x1 = ' ' + match.group(1) + ' '
        x2 = ' ' + match.group(3) + ' '
        y = ' ' + match.group(4) + ' '
        check = re.search(re.compile(x1), input_string)
        x1_fount = 0
        x2_fount = 0
        if check:
            input_string = input_string.replace(x1, ' ', 1)
            # print('x1 found')
            x1_fount = 1
        check = re.search(re.compile(x2), input_string)
        if check:
            input_string = input_string.replace(x2, y, 1)
            # print('x2 found')
            x2_fount = 1
        input_string = input_string.strip()
        input_string = input_string.replace('  ', ' ')
        print(input_string)
        if x1_fount and x2_fount:
            response = response + f' ( left: {input_string} )'
        else:
            response = 'wrong answer'
    else:
        print('wrong format')
        response = 'wrong answer'

    return response

def get_current_numbers(y: str) -> str:
    last_line = y.strip().split('\n')[-1]
    return ' ' + last_line.split('left: ')[-1].split(')')[0].strip() + ' '

def ksd(args, task, idx, to_print=True):
    global gpt, index
    index = idx
    x = task.get_input(idx)  # input
    d_thres = 10000 # a large number
    best_ans = ''
    best_path = set()
    level_nodes = [[] for _ in range(task.steps)]
    infos = []
    graph = tree_graph.graph(k = args.k, idx = idx)

    # x: question, y: (id, ans, value)
    for b in range(args.n_select_sample):
        gpt = partial(gpt, model=args.backend, temperature=args.temperature)
        print(gpt)
        y = (task.get_id(), '', 0)  # current output candidates
        path = set()
        distance = 0
        for step in range(task.steps - 1):
            # prune
            if distance > d_thres:
                record.Record_txt(record.record_file_name, '\n(prune)distance: ' + str(distance) + ', d_thres: ' + str(d_thres) + '\n\n', idx = idx)
                infos.append({'step': step, 'select_id': y[0], 'select_new_ys': y[1], 'values': y[2], 'is_best': False, 'is_back': True})
                break
            print(y[0])
            graph.visit_nodes([{'id': y[0]}])

            # Graph
            parent = y[0]
            graph.add_head_list_len(parent)
            # if has not visited yet
            if graph.tree_head[parent]['next_node']['node'] == None:
                # Generator
                record.Record_txt(record.record_file_name, '\n-----Generator-----\n\n', idx)
                new_ys = [get_proposals(task, x, y[1], args.k)]
                new_ys = list(itertools.chain(*new_ys))
                ids = [task.get_id() for _ in range(len(new_ys))]
                print(new_ys)
                record.Record_txt(record.record_file_name, '\nnew_ys after itertools\n' + '\n'.join(list(map(str, new_ys.copy()))), idx)
                record.Record_txt(record.record_file_name, '\n-----end Generator-----\n\n', idx)
                
                # Evaluator
                record.Record_txt(record.record_file_name, '\n-----Evaluator-----\n\n', idx)
                values = get_values(task, x, new_ys, args.n_evaluate_sample)
                print(values)
                record.Record_txt(record.record_file_name, '\nvalues:\n' + '\n'.join(list(map(str, values.copy()))) + '\n\n', idx)
                record.Record_txt(record.record_file_name, '\n-----end Evaluator-----\n\n', idx)
                new_ys = list(zip(ids, new_ys, values))
                # Sort
                new_ys = sorted(new_ys, key = lambda x: x[2], reverse = True)

                # Put nodes into graph
                new_nodes = list()
                for i in range(len(new_ys)):
                    node = {'id': new_ys[i][0], 'answer': new_ys[i][1], 'value': new_ys[i][2], 'parent_node': parent, 'ancestor_distance': distance}
                    new_nodes.append(node)
                graph.add_nodes(new_nodes)
                
                # Put outputs into level_nodes
                level_nodes[step].extend(new_ys.copy())
                level_nodes[step] = sorted(level_nodes[step], key = lambda x: x[2], reverse = True)

            # selection
            count = 0
            while graph.visited[level_nodes[step][count][0]] == 1:
                count += 1
            select_new_ys = [level_nodes[step][count]]
            distance = task.distance_calculator(select_new_ys[0][2], distance, args.n_evaluate_sample)

            print(select_new_ys)
            record.Record_txt(record.record_file_name, '\nselected nodes:\n' + '\n'.join(list(map(str, select_new_ys.copy()))) + '\n\n', idx)
            
            y = select_new_ys[0]
            path.add(y[0])
            infos.append({'step': step, 'select_id': y[0], 'select_new_ys': y[1], 'values': y[2], 'is_best': False, 'is_back': False})
        
        # Final Generator
        new_ys = [get_proposals(task, x, y[1], args.k)]
        new_ys = list(itertools.chain(*new_ys))
        ids = list(range(len(new_ys)))
        values = get_values(task, x, new_ys, args.n_evaluate_sample)
        top_id = sorted(ids, key=lambda x: values[x], reverse=True)[0]
        answer= new_ys[top_id]
        record.Record_txt(record.record_file_name, '\nanswer: ' + str(answer) + '\n\n', idx = idx)
        # save result and then back
        is_best = False
        if distance < d_thres:
            print('max')
            best_ans = answer
            best_path = path.copy()
            is_best = True
            # dfs with sphere decoding
            d_thres = distance
            record.Record_txt(record.record_file_name, '\nchange best answer\nbest_ans: ' + str(best_ans) + '\nd_thres: ' + str(d_thres) + '\n\n', idx = idx)
        infos.append({'step': step, 'select_id': y[0], 'select_new_ys': answer, 'values': values, 'is_best': is_best, 'is_back': False})

    graph.show_in_linked_list()
    graph.show_in_nodes()
    
    if to_print:
        print(infos)
    draw.dfs_Draw(task, args, infos, graph, idx, best_path)
    return [best_ans], {'steps': infos}, task.id