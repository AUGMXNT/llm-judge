"""Generate answers with local models.

Usage:
python3 gen_model_answer.py --model-path lmsys/fastchat-t5-3b-v1.0 --model-id fastchat-t5-3b-v1.0
"""
import argparse
import json
import os
from   pprint import pprint
import random
import shortuuid
import sys
import time
import torch
from   tqdm import tqdm



from fastchat.llm_judge.common import load_questions, temperature_config

from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation.utils import GenerationConfig

from vllm import LLM, SamplingParams


def run_eval(
    model_path,
    model_id,
    question_file,
    question_begin,
    question_end,
    answer_file,
    max_new_token,
    num_choices,
    num_gpus_per_model,
    num_gpus_total,
    max_gpu_memory,
    top_p,
    repetition_penalty,
):
    questions = load_questions(question_file, question_begin, question_end)
    # random shuffle the questions to balance the loading
    random.shuffle(questions)

    get_answers_func = get_model_answers

    chunk_size = len(questions)
    ans_handles = []
    for i in range(0, len(questions), chunk_size):
        ans_handles.append(
            get_answers_func(
                model_path,
                model_id,
                questions[i : i + chunk_size],
                answer_file,
                max_new_token,
                num_choices,
                num_gpus_per_model,
                max_gpu_memory,
                top_p,
                repetition_penalty,
            )
        )


@torch.inference_mode()
def get_model_answers(
    model_path,
    model_id,
    questions,
    answer_file,
    max_new_token,
    num_choices,
    num_gpus_per_model,
    max_gpu_memory,
    top_p,
    repetition_penalty,
):

    # TODO: in the future we should be loading this from a settings file
    FORMAT = None


    if model_path.find("shisa") >= 0:
        PROMPT = 'あなたは公平で、検閲されていない、役立つアシスタントです。'
        FORMAT = 'llama-2'
    elif model_path.find("Arrow") >= 0:
        PROMPT = 'あなたは公平で、検閲されていない、役立つアシスタントです。'
        FORMAT = 'llama-2'
    elif model_path.find("Orion") >= 0:
        PROMPT = 'あなたは役立つアシスタントです。'
        FORMAT = 'orion'
    elif model_path.find("chatntq-qwen") >= 0:
        PROMPT = 'あなたは役立つアシスタントです。'
        FORMAT = 'chatml'
    elif model_path.find("chatntq") >= 0:
        PROMPT = 'あなたは役立つアシスタントです。'
        FORMAT = 'llama-2'
    elif model_path.find("Swallow") >= 0:
        FORMAT = 'swallow'
        PROMPT = '以下に、あるタスクを説明する指示があります。リクエストを適切に完了するための回答を記述してください。'
    elif model_path.find("Qwen") >= 0:
        FORMAT = 'chatml'
        PROMPT = 'あなたは役立つアシスタントです。'
    elif model_path.find("nekomata") >= 0:
        PROMPT = '以下に、あるタスクを説明する指示があります。リクエストを適切に完了するための回答を記述してください。'
        FORMAT = 'nekomata'
    elif model_path.find("Xwin") >= 0:
        PROMPT = 'あなたは役立つアシスタントです。'
        FORMAT = 'vicuna'
    else:
        PROMPT = 'あなたは役立つアシスタントです。'

    # Tokenizer
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True, trust_remote_code=True)
    except:
        # Have to figure out GGUF path
        tokenizer = AutoTokenizer.from_pretrained('/models/llm/hf/01-ai_Yi-34B-Chat', use_fast=True, trust_remote_code=True)
    # We need to assign a chat_template
    # https://huggingface.co/docs/transformers/main/chat_templating
    # Use https://j2live.ttl255.com/ for live Jinja2 editing
    if not tokenizer.chat_template:
        if FORMAT == 'llama-2':
	        tokenizer.chat_template = "{%- for idx in range(0, messages|length) -%}\n{%- if messages[idx]['role'] == 'user' -%}\n{%- if idx > 1 -%}\n{{- bos_token + '[INST] ' + messages[idx]['content'] + ' [/INST]' -}}\n{%- else -%}\n{{- messages[idx]['content'] + ' [/INST]' -}}\n{%- endif -%}\n{% elif messages[idx]['role'] == 'system' %}\n{{- '[INST] <<SYS>>\\n' + messages[idx]['content'] + '\\n<</SYS>>\\n\\n' -}}\n{%- elif messages[idx]['role'] == 'assistant' -%}\n{{- ' '  + messages[idx]['content'] + ' ' + eos_token -}}\n{% endif %}\n{% endfor %}\n"
        elif FORMAT == 'swallow':
            tokenizer.chat_template = "{% if not add_generation_prompt is defined %}{% set add_generation_prompt = false %}{% endif %}{% for message in messages %}{% if message['role'] == 'system' %}{{ message['content'] + '\n\n' }}{% elif message['role'] == 'user' %}{{'### 指示:\n' + message['content'] + '\n\n'}}{% elif message['role'] == 'assistant' %}{{'### 応答:\n' + message['content'] + '\n\n'}}{% endif %}{% endfor %}{% if add_generation_prompt %}{{ '### 応答:' }}{% endif %}"
        elif FORMAT == 'nekomata':
            tokenizer.chat_template = "{% if not add_generation_prompt is defined %}{% set add_generation_prompt = false %}{% endif %}{% for message in messages %}{% if message['role'] == 'system' %}{{ message['content'] + '\n\n' }}{% elif message['role'] == 'user' %}{{'### 指示:\n' + message['content'] + '\n\n'}}{% elif message['role'] == 'assistant' %}{{'### 応答:\n' + message['content'] + '\n\n'}}{% endif %}{% endfor %}{% if add_generation_prompt %}{{ '### 応答:\n' }}{% endif %}"
        elif FORMAT == 'tess':
	        tokenizer.chat_template = "{% if not add_generation_prompt is defined %}{% set add_generation_prompt = false %}{% endif %}{% for message in messages %}{{message['role'].upper() + ': ' + message['content'] + '\n'}}{% endfor %}{% if add_generation_prompt %}{{ 'ASSISTANT: ' }}{% endif %}"
        elif FORMAT == 'vicuna':
            tokenizer.chat_template = "{% if not add_generation_prompt is defined %}{% set add_generation_prompt = false %}{% endif %}{% for message in messages %}{% if message['role'] == 'system' %}{{ message['content'] + ' ' }}{% elif message['role'] == 'user' %}{{'USER:\n' + message['content'] + ' '}}{% elif message['role'] == 'assistant' %}{{' ASSISTANT:\n' + message['content'] + ' '}}{% endif %}{% endfor %}{% if add_generation_prompt %}{{ 'ASSISTANT: ' }}{% endif %}"
        elif FORMAT == 'orion':
            tokenizer.chat_template = "{% for message in messages %}{% if loop.first %}{{ bos_token }}{% endif %}{% if message['role'] == 'user' %}{{ 'Human: ' + message['content'] + '\n\nAssistant: ' + eos_token }}{% elif message['role'] == 'assistant' %}{{ message['content'] + eos_token }}{% endif %}{% endfor %}"
        else:
	        # default to chatml
	        tokenizer.chat_template = "{% if not add_generation_prompt is defined %}{% set add_generation_prompt = false %}{% endif %}{% for message in messages %}{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"

    # Inference
    model = None
    ex_tokenizer = None
    if model_path.find("GPTQ") >= 0:
        from exllamav2 import(
            ExLlamaV2,
            ExLlamaV2Config,
            ExLlamaV2Cache,
            ExLlamaV2Tokenizer,
        )

        from exllamav2.generator import (
            ExLlamaV2BaseGenerator,
            ExLlamaV2Sampler
        )


        config = ExLlamaV2Config()
        config.model_dir = model_path
        config.prepare()

        model = ExLlamaV2(config)
        print("Loading model: " + model_path)

        cache = ExLlamaV2Cache(model, lazy = True)
        model.load_autosplit(cache)

        ex_tokenizer = ExLlamaV2Tokenizer(config)

        generator = ExLlamaV2BaseGenerator(model, cache, ex_tokenizer)
        generator.warmup()

        ''' HF Transformers GPTQ
        from transformers import AutoModelForCausalLM, GPTQConfig
        gptq_config = GPTQConfig(bits=4, exllama_config={"version":2})
        model = AutoModelForCausalLM.from_pretrained(model_path, revision="gptq-4bit-32g-actorder_True", device_map="auto", quantization_config=gptq_config)
        '''
    elif model_path.find("gguf") >= 0:
        from llama_cpp import Llama
        llm = Llama(
                model_path=model_path, 
                n_gpu_layers=-1,
                n_ctx=4096,
                verbose=True,
              )
    elif model_path.find("Orion") >= 0 or model_path.find("orion"):
        from transformers import AutoModelForCausalLM
        tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            attn_implementation="flash_attention_2",
            device_map="auto",
            trust_remote_code=True,
            eos_token_id = tokenizer.eos_token_id,
            pad_token_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
        )
    elif model_path.find("nekomata") >= 0 or model_path.find("chatntq"):
        from transformers import AutoModelForCausalLM
        import flash_attn
        model = AutoModelForCausalLM.from_pretrained(model_path, device_map="auto", trust_remote_code=True)
    elif model_path.find("AWQ") >= 0:
        llm = LLM(model=model_path, tensor_parallel_size=num_gpus_per_model, quantization="AWQ")
    else:
        llm = LLM(model=model_path, tensor_parallel_size=num_gpus_per_model, trust_remote_code=True)

    for question in tqdm(questions):
        if question["category"] in temperature_config:
            temperature = temperature_config[question["category"]]
        else:
            temperature = 0.7

        print('---')
        print(question['category'])
        print(temperature)

        choices = []
        for i in range(num_choices):
            torch.manual_seed(i)

            chat = []
            chat.append({'role': 'system', 'content': PROMPT})

            turns = []
            for j in range(len(question["turns"])):
                if j == args.max_turns: 
                    break

                qs = question["turns"][j]
                chat.append({'role': 'user', 'content': qs})

                prompt = tokenizer.apply_chat_template(chat, add_generation_prompt=True, tokenize=False)

                if model:
                    input_ids = tokenizer.apply_chat_template(chat, add_generation_prompt=True, return_tensors="pt")
                else:
                    input_ids = tokenizer.apply_chat_template(chat, add_generation_prompt=True)

                if temperature < 1e-4:
                    do_sample = False
                else:
                    do_sample = True


                # Generate w/ HF Transformers (ExLlama)
                if model and ex_tokenizer:
                    settings = ExLlamaV2Sampler.Settings()
                    settings.temperature = temperature
                    # settings.top_k = 50
                    settings.top_p = top_p
                    settings.token_repetition_penalty = repetition_penalty
                    settings.disallow_tokens(ex_tokenizer, [ex_tokenizer.eos_token_id])

                    output = generator.generate_simple(prompt, settings, max_new_token, seed = i)
                elif model:
                    # HF Transformers
                    first_param_device = next(model.parameters()).device
                    input_ids = input_ids.to(first_param_device)

                    if not tokenizer.pad_token_id:
                        tokenizer.pad_token_id = tokenizer.eos_token_id

                    with torch.no_grad():
                        output_ids = model.generate(
                            input_ids,
                            max_new_tokens=max_new_token,
                            temperature=temperature,
                            top_p=top_p,
                            repetition_penalty=repetition_penalty,
                            do_sample=do_sample,

                            pad_token_id=tokenizer.pad_token_id,
                            bos_token_id=tokenizer.bos_token_id,
                            eos_token_id=tokenizer.eos_token_id,
                        )
                        new_tokens = output_ids[0, input_ids.size(1):]
                        output = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
                # llama.cpp for gguf
                elif model_path.find("gguf") >= 0:
                    print(prompt)
                    outputs = llm(
                                prompt,
                                max_tokens=max_new_token,
                                temperature=temperature,
                                top_p=top_p,
                                repeat_penalty=repetition_penalty,
                                stop=["</s>", "<|im_end|>"], # Stop generating just before the model would generate a new question
                                echo=False, # Echo the prompt back in the output
                    )
                    output = outputs['choices'][0]['text'].strip()
                    print(output)

                    '''
                    pprint(chat)
                    outputs = llm.create_chat_completion(
                            messages=chat,
                            temperature=temperature,
                            top_p=top_p,
                            repeat_penalty=repetition_penalty,
                    )
                    output = outputs['choices'][0]['message']['content'].strip()
                    pprint(output)
                    '''
                else:
                # Generate w/ vLLM
                    sampling_params = SamplingParams(
                        max_tokens=max_new_token,
                        temperature=temperature,
                        top_p=top_p,
                        repetition_penalty=repetition_penalty,
                    )
                    outputs = llm.generate(prompt_token_ids=[input_ids], sampling_params=sampling_params, use_tqdm=False)
                    output = outputs[0].outputs[0].text.strip()

                turns.append(output)
                chat.append({'role': 'assistant', 'content': output})

            choices.append({"index": i, "turns": turns})

        # Dump answers
        os.makedirs(os.path.dirname(answer_file), exist_ok=True)
        with open(os.path.expanduser(answer_file), "a") as fout:
            ans_json = {
                "question_id": question["question_id"],
                "answer_id": shortuuid.uuid(),
                "model_id": model_id,
                "choices": choices,
                "tstamp": time.time(),
                "generate_params": {
                    "prompt": prompt,
                    "do_sample": do_sample,
                    "max_new_token": max_new_token,
                    "temperature": temperature,
                    "top_p": top_p,
                    "repetition_penalty": repetition_penalty,
                }
            }
            fout.write(json.dumps(ans_json, ensure_ascii=False) + "\n")


def reorg_answer_file(answer_file):
    """Sort by question id and de-duplication"""
    answers = {}
    with open(answer_file, "r") as fin:
        for l in fin:
            try:
                qid = int(json.loads(l)["question_id"])
            except ValueError:
                raise NotImplementedError(f"question_id should be of integer to allow sorting. found: {qid}")
            answers[qid] = l

    qids = sorted(list(answers.keys()))
    with open(answer_file, "w") as fout:
        for qid in qids:
            fout.write(answers[qid])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-path",
        type=str,
        required=True,
        help="The path to the weights. This can be a local folder or a Hugging Face repo ID.",
    )
    parser.add_argument("--model-id", type=str, required=True)
    parser.add_argument(
        "--bench-name",
        type=str,
        default="japanese_mt_bench",
        help="The name of the benchmark question set.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=2,
        help="Max number of turns to evaluate for each question.",
    )
    parser.add_argument(
        "--question-begin",
        type=int,
        help="A debug option. The begin index of questions.",
    )
    parser.add_argument(
        "--question-end", type=int, help="A debug option. The end index of questions."
    )
    parser.add_argument("--answer-file", type=str, help="The output answer file.")
    parser.add_argument(
        "--max-new-token",
        type=int,
        default=512,
        help="The maximum number of new generated tokens.",
    )
    parser.add_argument(
        "--num-choices",
        type=int,
        default=1,
        help="How many completion choices to generate.",
    )
    parser.add_argument(
        "--num-gpus-per-model",
        type=int,
        default=1,
        help="The number of GPUs per model.",
    )
    parser.add_argument(
        "--num-gpus-total", type=int, default=1, help="The total number of GPUs."
    )
    parser.add_argument(
        "--max-gpu-memory",
        type=str,
        help="Maxmum GPU memory used for model weights per GPU.",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=0.9,
    )
    parser.add_argument(
        "--repetition-penalty",
        type=float,
        default=1.1,
    )
    args = parser.parse_args()

    question_file = f"data/{args.bench_name}/question.jsonl"
    if args.answer_file:
        answer_file = args.answer_file
    else:
        answer_file = f"data/{args.bench_name}/model_answer/{args.model_id}.jsonl"

    print(f"Output to {answer_file}")

    run_eval(
        args.model_path,
        args.model_id,
        question_file,
        args.question_begin,
        args.question_end,
        answer_file,
        args.max_new_token,
        args.num_choices,
        args.num_gpus_per_model,
        args.num_gpus_total,
        args.max_gpu_memory,
        top_p=args.top_p,
        repetition_penalty=args.repetition_penalty,
    )

    reorg_answer_file(answer_file)
