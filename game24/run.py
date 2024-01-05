import pandas as pd
import json
import parameters
import llm_function
import game24_draw as draw
from bfs import *
import record_function as record
import sympy
import re
import time


def Acc(answer, data, puzzles_id):
    numbers = re.findall(r'\d+', answer)
    problem_numbers = re.findall(r'\d+', data['Puzzles'][puzzles_id])
    if sorted(numbers) != sorted(problem_numbers):
        return False
    return bool(sympy.simplify(answer) == 24)


if __name__ == '__main__':
    # initialize
    data_game24 = pd.read_csv(parameters.data_path_game24)
    llm = llm_function.get_llm()
    locs = list()

    print('llm ok')
    record.Init_record_file(parameters.all_json_file_name, '')
    parameters.reset_idx()
    for i in range(parameters.initial_idx, parameters.initial_idx + parameters.question_sets):
        #call llm
        start_time = time.time()
        nodes = [{'id': parameters.id, 'answer': data_game24['Puzzles'][i], 'value': None, 'parent_node': None, 'ancestor_value': None}]
        parameters.increase_id()
        loc = bfs(llm, nodes)
        end_time = time.time()
        # record
        loc['id'] = i
        loc['correct'] = Acc(loc['answer'], data_game24, i)
        loc['cost time'] = end_time - start_time
        locs.append(loc)
        record.Record_json(parameters.json_file_name, locs)
        print(loc)
        parameters.increase_idx()
        parameters.reset_id()
    record.Record_json(parameters.all_json_file_name, locs)
    # draw
    draw.Draw(parameters.all_json_file_name.format(file_path = parameters.record_files_folder))
