from huggingface_hub import hf_hub_download, login
import os


def Model_download(repo_id, filename, local_dir):
    login(token = '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')

    if not os.path.exists(local_dir):
            os.makedirs(local_dir)
    
    hf_hub_download(
        repo_id = repo_id,
        filename = filename,
        local_dir = local_dir
    )