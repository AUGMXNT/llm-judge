# llm-judge
A faster compatible implementation of LM-SYS FastChat [llm-judge](https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge) and derivatives

We switch to the fastest inference engine depending on format:
* HF: vLLM
* AWQ: vLLM
* GPTQ: ExLlamaV2

## Install
We use `mamba` ([install instructions](https://github.com/conda-forge/miniforge?tab=readme-ov-file#install)) to run.

```
mamba create -n llm-judge python=3.11
git clone https://github.com/AUGMXNT/llm-judge
cd llm-judge
```

## TODO
```
# 4090+3090:
* Original: 8h for 13b... wtf

# V0: Just faster inferences
[x] Just rip out for fast vLLM first
* real    16m35.112s


# AutoAWQ vs vLLM
* vLLM uses more memory than it should
* How's the speed? https://github.com/casper-hansen/AutoAWQ

# Add GGUF support
[ ] python-llama-cpp

# Batching
First Pass:
[x] Organize by Temperature

We actually should thread our queries, since we have multiturn to deal with
We can easily batch the choices together (but maybe shouldn't for seeding purposes)

A real PITA which we don't need.

Better UI
[ ] InquirerPy
[ ] Add Config Files
[ ] Look at https://github.com/AUGMXNT/gpt4-autoeval
[ ] Run logging
[ ] Run autoresume
```
