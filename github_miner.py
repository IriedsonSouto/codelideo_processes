import requests
import json
import os
import re
import time
import threading
import signal
import sys
import random
from queue import Queue, Empty

# Carregar configuração
with open('config.json') as config_file:
    config = json.load(config_file)

GITHUB_TOKEN = config['github_token']
REPOS = config['repos']
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}', 'User-Agent': 'MyApp/1.0'}
MAX_THREADS = 5
stop_event = threading.Event()
queue = Queue()

SYSTEM_MESSAGES = [
    "Por favor, revise o código a seguir:",  # Português
    "Confira o código abaixo e forneça seus comentários:",  # Português
    "Revise o trecho de código a seguir:",  # Português
    "Dê uma olhada neste código e sugira melhorias:",  # Português
    "Analise o código abaixo e compartilhe sua opinião:",  # Português
    "Please review the following code:",  # Inglês
    "Check the code below and provide your comments:",  # Inglês
    "Review the code snippet below:",  # Inglês
    "Take a look at this code and suggest improvements:",  # Inglês
    "Analyze the code below and share your feedback:"  # Inglês
]

def get_rate_limit():
    url = "https://api.github.com/rate_limit"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()['rate']['remaining'], response.json()['rate']['reset']
    except requests.RequestException as e:
        print(f"Erro ao obter limite de taxa: {e}")
    return 0, time.time() + 60

def rate_limit_guard():
    while not stop_event.is_set():
        remaining, reset_time = get_rate_limit()
        if remaining == 0:
            sleep_time = reset_time - time.time()
            if sleep_time > 0:
                print(f"Limite de taxa atingido. Aguardando {sleep_time} segundos.")
                time.sleep(sleep_time + 1)
        time.sleep(1)

def get_pull_request_comments(owner, repo):
    comments = []
    page = 1
    while not stop_event.is_set():
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/comments?page={page}"
        print(f"Obtendo comentários de revisão da página {page} de {owner}/{repo}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            current_page_comments = response.json()
            if not current_page_comments:
                break
            comments.extend(current_page_comments)
            page += 1
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as err:
            print(f"Erro ao obter comentários de revisão de {owner}/{repo}: {err}")
            time.sleep(5)
    return comments

def extract_diff_hunks(diff_text):
    return re.findall(r'@@.*?@@\n(?:.*\n)+?', diff_text)

def remove_comments_from_code(code):
    # Remove comentários de linha
    code = re.sub(r'//.*', '', code)
    # Remove comentários de bloco
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    return code

def process_repo(owner, repo_name):
    print(f"Processando repositório: {owner}/{repo_name}")

    comments = get_pull_request_comments(owner, repo_name)
    if stop_event.is_set():
        print(f"Processamento interrompido para o repositório: {owner}/{repo_name}")
        return

    print(f"Encontrados {len(comments)} comentários de revisão em {owner}/{repo_name}")

    data = []
    for comment in comments:
        if stop_event.is_set():
            print(f"Processamento interrompido para o repositório: {owner}/{repo_name}")
            return

        pr_url = comment['pull_request_url']
        diff_hunk = comment['diff_hunk']
        comment_body = comment['body']

        # Limpar o código dos comentários
        cleaned_diff_hunk = remove_comments_from_code(diff_hunk)

        # Selecionar uma mensagem de sistema aleatória
        system_message = random.choice(SYSTEM_MESSAGES)

        entry = {
            "project_name": f"{owner}/{repo_name}",
            "pull_request_url": pr_url,
            "diff_hunk": cleaned_diff_hunk,
            "comments": comment_body,
            "prompt": f"<s>[INST] <<SYS>>\n{system_message}\n<</SYS>>{cleaned_diff_hunk} [/INST]{comment_body} </s>"
        }
        data.append(entry)

    # Salvar os dados em arquivos JSON divididos
    if not os.path.exists('output'):
        os.makedirs('output')

    file_index = 1
    output_filename = f'output/{owner}_{repo_name}_{file_index}.json'
    while os.path.exists(output_filename):
        file_index += 1
        output_filename = f'output/{owner}_{repo_name}_{file_index}.json'

    with open(output_filename, 'w') as f:
        json.dump(data, f, indent=4)

    print(f"Dados salvos em {output_filename}")

def worker():
    while not stop_event.is_set():
        try:
            owner, repo_name = queue.get_nowait()
        except Empty:
            return
        process_repo(owner, repo_name)
        queue.task_done()

def process_repos():
    for repo in REPOS:
        queue.put((repo['owner'], repo['repo']))

    rate_limit_thread = threading.Thread(target=rate_limit_guard)
    rate_limit_thread.start()

    threads = []
    for _ in range(min(MAX_THREADS, queue.qsize())):
        thread = threading.Thread(target=worker)
        threads.append(thread)
        thread.start()

    queue.join()
    stop_event.set()

    for thread in threads:
        thread.join()
    rate_limit_thread.join()

def signal_handler(sig, frame):
    print('Interrupção recebida! Encerrando o processo...')
    stop_event.set()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    process_repos()

if __name__ == "__main__":
    main()
