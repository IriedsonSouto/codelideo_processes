import time
import json
import os
import random
import re
import string
from functools import partial
from multiprocessing import Pool

import numpy as np
import tqdm
from rouge_score import rouge_scorer
import utils
import openai

# Configuração
with open('config.json') as config_file:
    config = json.load(config_file)

OPENAI_API_KEY = config['openai_api_key']
openai.api_key = OPENAI_API_KEY

OUTPUT_DIR = "./generated_output"
SEED_TASKS_PATH = "./filtered_output/filtered_data_1.json"
NUM_INSTRUCTIONS_TO_GENERATE = 100
MODEL_NAME = "gpt-3.5-turbo"
NUM_PROMPT_INSTRUCTIONS = 3
REQUEST_BATCH_SIZE = 5
TEMPERATURE = 1.0
TOP_P = 1.0
NUM_CPUS = 16

def encode_prompt(prompt_instructions):
    """Encode multiple prompt instructions into a single string."""
    prompt = open("./prompt.txt").read() + "\n"

    for idx, task_dict in enumerate(prompt_instructions):
        (instruction, input, output) = task_dict["instruction"], task_dict["input"], task_dict["output"]
        instruction = re.sub(r"\s+", " ", instruction).strip().rstrip(":")
        input = "<noinput>" if input.lower() == "" else input
        prompt += f"###\n"
        prompt += f"{idx + 1}. Instruction: {instruction}\n"
        prompt += f"{idx + 1}. Input:\n{input}\n"
        prompt += f"{idx + 1}. Output:\n{output}\n"
    prompt += f"###\n"
    prompt += f"{idx + 2}. Instruction:"
    return prompt

def post_process_gpt3_response(num_prompt_instructions, response):
    if response is None:
        return []
    raw_instructions = f"{num_prompt_instructions+1}. Instruction:" + response["text"]
    raw_instructions = re.split("###", raw_instructions)
    instructions = []
    for idx, inst in enumerate(raw_instructions):
        if idx == len(raw_instructions) - 1 and response["finish_reason"] == "length":
            continue
        idx += num_prompt_instructions + 1
        splitted_data = re.split(f"{idx}\.\s+(Instruction|Input|Output):", inst)
        if len(splitted_data) != 7:
            continue
        else:
            inst = splitted_data[2].strip()
            input = splitted_data[4].strip()
            input = "" if input.lower() == "<noinput>" else input
            output = splitted_data[6].strip()
        if len(inst.split()) <= 3 or len(inst.split()) > 150:
            continue
        blacklist = [
            "image",
            "images",
            "graph",
            "graphs",
            "picture",
            "pictures",
            "file",
            "files",
            "map",
            "maps",
            "draw",
            "plot",
            "go to",
            "video",
            "audio",
            "music",
            "flowchart",
            "diagram",
        ]
        blacklist += []
        if any(find_word_in_string(word, inst) for word in blacklist):
            continue
        if inst.startswith("Write a program"):
            continue
        if inst[0] in string.punctuation:
            continue
        if not inst[0].isascii():
            continue
        instructions.append({"instruction": inst, "input": input, "output": output})
    return instructions

def find_word_in_string(w, s):
    return re.compile(r"\b({0})\b".format(w), flags=re.IGNORECASE).search(s)

def generate_code_review_data():
    seed_tasks = [json.loads(l) for l in open(SEED_TASKS_PATH, "r")]
    seed_instruction_data = [
        {"instruction": t["instruction"], "input": t["input"], "output": t["output"]}
        for t in seed_tasks
    ]
    print(f"Loaded {len(seed_instruction_data)} human-written seed instructions")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    request_idx = 0
    machine_instruction_data = []
    if os.path.exists(os.path.join(OUTPUT_DIR, "regen.json")):
        machine_instruction_data = utils.jload(os.path.join(OUTPUT_DIR, "regen.json"))
        print(f"Loaded {len(machine_instruction_data)} machine-generated instructions")

    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)

    progress_bar = tqdm.tqdm(total=NUM_INSTRUCTIONS_TO_GENERATE)
    if machine_instruction_data:
        progress_bar.update(len(machine_instruction_data))

    all_instructions = [d["instruction"] for d in seed_instruction_data] + [
        d["instruction"] for d in machine_instruction_data
    ]
    all_instruction_tokens = [scorer._tokenizer.tokenize(inst) for inst in all_instructions]

    while len(machine_instruction_data) < NUM_INSTRUCTIONS_TO_GENERATE:
        request_idx += 1

        batch_inputs = []
        for _ in range(REQUEST_BATCH_SIZE):
            prompt_instructions = random.sample(seed_instruction_data, NUM_PROMPT_INSTRUCTIONS)
            prompt = encode_prompt(prompt_instructions)
            batch_inputs.append(prompt)
        decoding_args = utils.OpenAIDecodingArguments(
            temperature=TEMPERATURE,
            n=1,
            max_tokens=3072,
            top_p=TOP_P,
            stop=["\n20", "20.", "20."],
        )
        request_start = time.time()
        results = utils.openai_completion(
            prompts=batch_inputs,
            model_name=MODEL_NAME,
            batch_size=REQUEST_BATCH_SIZE,
            decoding_args=decoding_args,
            logit_bias={"50256": -100},
        )
        request_duration = time.time() - request_start

        process_start = time.time()
        instruction_data = []
        for result in results:
            new_instructions = post_process_gpt3_response(NUM_PROMPT_INSTRUCTIONS, result)
            instruction_data += new_instructions

        total = len(instruction_data)
        keep = 0
        for instruction_data_entry in instruction_data:
            new_instruction_tokens = scorer._tokenizer.tokenize(instruction_data_entry["instruction"])
            with Pool(NUM_CPUS) as p:
                rouge_scores = p.map(
                    partial(rouge_scorer._score_lcs, new_instruction_tokens),
                    all_instruction_tokens,
                )
            rouge_scores = [score.fmeasure for score in rouge_scores]
            most_similar_instructions = {
                all_instructions[i]: rouge_scores[i] for i in np.argsort(rouge_scores)[-10:][::-1]
            }
            if max(rouge_scores) > 0.7:
                continue
            else:
                keep += 1
            instruction_data_entry["most_similar_instructions"] = most_similar_instructions
            instruction_data_entry["avg_similarity_score"] = float(np.mean(rouge_scores))
            machine_instruction_data.append(instruction_data_entry)
            all_instructions.append(instruction_data_entry["instruction"])
            all_instruction_tokens.append(new_instruction_tokens)
            progress_bar.update(1)
        process_duration = time.time() - process_start
        print(f"Request {request_idx} took {request_duration:.2f}s, processing took {process_duration:.2f}s")
        print(f"Generated {total} instructions, kept {keep} instructions")
        utils.jdump(machine_instruction_data, os.path.join(OUTPUT_DIR, "regen.json"))

if __name__ == "__main__":
    generate_code_review_data()
