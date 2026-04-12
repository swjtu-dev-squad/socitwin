---
library_name: peft
license: other
base_model: D:\LLaMA-Factory-main\Qwen2.5-0.5B-Instruct
tags:
- base_model:adapter:D:\LLaMA-Factory-main\Qwen2.5-0.5B-Instruct
- llama-factory
- lora
- transformers
pipeline_tag: text-generation
model-index:
- name: out_nlp
  results: []
---

<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->

# out_nlp

This model is a fine-tuned version of [D:\LLaMA-Factory-main\Qwen2.5-0.5B-Instruct](https://huggingface.co/D:\LLaMA-Factory-main\Qwen2.5-0.5B-Instruct) on the miao2 dataset.

## Model description

More information needed

## Intended uses & limitations

More information needed

## Training and evaluation data

More information needed

## Training procedure

### Training hyperparameters

The following hyperparameters were used during training:
- learning_rate: 5e-05
- train_batch_size: 1
- eval_batch_size: 8
- seed: 42
- gradient_accumulation_steps: 2
- total_train_batch_size: 2
- optimizer: Use adamw_torch_fused with betas=(0.9,0.999) and epsilon=1e-08 and optimizer_args=No additional optimizer arguments
- lr_scheduler_type: cosine
- lr_scheduler_warmup_steps: 50
- num_epochs: 5
- mixed_precision_training: Native AMP

### Training results



### Framework versions

- PEFT 0.17.1
- Transformers 4.57.1
- Pytorch 2.10.0.dev20251023+cu128
- Datasets 4.0.0
- Tokenizers 0.22.1