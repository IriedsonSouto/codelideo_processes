# GitHub Mining Project 

Este projeto tem como objetivo minerar comentários de revisão de repositórios GitHub e processá-los para uso em treinamentos de modelos de linguagem. O projeto é dividido em duas partes principais: coleta e mineração de dados dos repositórios GitHub, e a seleção de um subconjunto desses dados.

## :books: Requisitos

1. **Python 3.7+**
2. **Bibliotecas Python**: `requests`, `json`, `os`, `re`, `time`, `threading`, `signal`, `random`, `queue`
3. **Um token de API do GitHub**

## :hammer_and_wrench: Configuração

1. **Clone o repositório**:
   ```sh
   git clone https://github.com/IriedsonSouto/minerador_github.git
   ```

2. **Instale as dependências**:
    ```sh
   pip install -r requirements.txt
   ```

3. **Configure o arquivo config.json**:

    Replique o exemplo 'config_example.json' informe os repositórios que deseja minerar e o seu token github

## :play_or_pause_button: Execução

1. **Mineração de Comentários de Revisão**:
   ```sh
   python github_miner.py
   ```
    O script irá:

    - Coletar comentários de revisão dos repositórios listados.
    - Limpar o código dos comentários.
    - Salvar os dados processados no diretório output/.

2. **Seleção de Subconjunto de Dados**:
   ```sh
   python filter_and_split_json.py
   ```
    O script irá:

    - Ler todos os arquivos JSON no diretório output/.
    - Selecionar aleatoriamente 250 itens (com base nos critérios especificados).
    - Salvar o subconjunto no diretório filtered_output/.
