# llm-judge
A faster compatible implementation of LM-SYS FastChat [llm-judge](https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge) and derivatives

## Install
We use `mamba` ([install instructions](https://github.com/conda-forge/miniforge?tab=readme-ov-file#install)) to run.

```
mamba create -n llm-judge python=3.11
git clone https://github.com/AUGMXNT/llm-judge
cd llm-judge
```

## TODO
```
4090+3090:
* Original: 4h+ for 13b...

V0: Just faster inferences
[x] Just rip out for fast vLLM first
* real    16m35.112s



V1: Batching
First Pass:
[x] Organize by Temperature

We actually should thread our queries, since we have multiturn
We can easily batch the choices together (but maybe shouldn't for seeding purposes)

A real PITA which we don't need.
```



[ ] Look at https://github.com/AUGMXNT/japanese-llm-ranking/tree/main
[ ] InquirerPy https://github.com/AUGMXNT/gpt4-autoeval
[ ] Add Config Files
[ ] Look at https://github.com/AUGMXNT/gpt4-autoeval

Make sure we can run other inference engines
[ ] Make sure we can batch (group by sampling)
[ ] python-llama-cpp
[ ] ExLlamaV2
* Attach response
* Attach response
