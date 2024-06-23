import os
import json

# Configurações
INPUT_DIR = 'filtered_output'
OUTPUT_FILE = 'filtered_output/relevant_comments.json'

# Palavras-chave relevantes para identificar comentários colaborativos
RELEVANT_KEYWORDS = ["should", "recommend", "suggest", "could", "might", "if", "need", "find", "keep", "note", "better", "improve", "refactor", "consider", "optimization", "fix"]

def load_json_file(input_dir):
    data = []
    for filename in os.listdir(input_dir):
        if filename.endswith('filtered_data_1.json'):
            filepath = os.path.join(input_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as file:
                file_data = json.load(file)
                data.extend(file_data)
    return data

def filter_relevant_comments(data):
    return [
        entry for entry in data if any(
            keyword in entry['comments'].lower() for keyword in RELEVANT_KEYWORDS
        ) and "thank" not in entry['comments'].lower()
    ]

def save_filtered_data(data, output_file):
    # Verificar se o arquivo de saída já existe e, se existir, excluí-lo
    if os.path.exists(output_file):
        os.remove(output_file)

    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
    print(f"Filtered comments have been written to {output_file}")

def main():
    # Carregar o arquivo JSON da pasta filtered_output
    all_data = load_json_file(INPUT_DIR)

    # Filtrar os comentários relevantes
    filtered_data = filter_relevant_comments(all_data)

    # Salvar os dados filtrados em um novo arquivo JSON na pasta filtered_output
    save_filtered_data(filtered_data, OUTPUT_FILE)

if __name__ == "__main__":
    main()
