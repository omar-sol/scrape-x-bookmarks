import os
import json

import gradio as gr
import pandas as pd
import numpy as np
import cohere
from dotenv import load_dotenv

load_dotenv()


def load_or_initialize_json(filepath, default=None):
    if default is None:
        default = []
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return default


SCRAPED_CONTENTS_FILE = "scraped_contents.json"
scraped_contents = load_or_initialize_json(SCRAPED_CONTENTS_FILE)


def cosine_similarity_matrix(vectors, query_vec):
    dot_product = np.dot(vectors, query_vec)

    norms_vectors = np.linalg.norm(vectors, axis=1)
    norm_query_vec = np.linalg.norm(query_vec)

    if norm_query_vec == 0 or np.any(norms_vectors == 0):
        raise ValueError(
            "Cosine similarity is not defined when one or both vectors are zero vectors."
        )

    similarity = dot_product / (norms_vectors * norm_query_vec)
    return similarity


def user(user_input, history):
    """Adds user's question immediately to the chat."""
    return "", history + [[user_input, None]]


def get_answer(history):
    model_name = "embed-english-v3.0"

    api_key: str | None = os.getenv("COHERE_API_KEY")
    if api_key is None:
        raise ValueError("Please set your COHERE_API_KEY environment variable.")
    input_type_embed = "search_query"
    # QUERY = "RAG system, LLMs, retrieval augmented generation, language models"
    QUERY = history[-1][0]

    # Now we'll set up the cohere client.
    co = cohere.Client(api_key)

    # Get the embeddings
    query_embed = co.embed(
        texts=[QUERY], model=model_name, input_type=input_type_embed
    ).embeddings
    query_embed = np.array(query_embed)
    query_embed = query_embed.reshape(-1)

    embeds_dataset = np.load("embeddings.npy")

    similarity_results = np.zeros((embeds_dataset.shape[0],), dtype=np.float32)
    try:
        similarity_results = cosine_similarity_matrix(embeds_dataset, query_embed)
    except ValueError as e:
        print(e)

    sorted_indices = np.argsort(similarity_results)[::-1]
    history[-1][1] = ""
    for i in range(25):
        print(
            similarity_results[sorted_indices[i]], scraped_contents[sorted_indices[i]]
        )
        history[-1][1] += scraped_contents[sorted_indices[i]]["link"]
        history[-1][1] += "\n"
        history[-1][1] += scraped_contents[sorted_indices[i]]["content"]
        history[-1][1] += "\n\n"

    return history


with gr.Blocks() as demo:
    with gr.Row():
        latest_completion = gr.State()
        chatbot = gr.Chatbot(elem_id="chatbot", show_copy_button=True)
    with gr.Row():
        question = gr.Textbox(
            label="Search X posts",
            placeholder="Type search query here...",
            lines=1,
        )
        submit = gr.Button(value="Send", variant="secondary")

    completion = gr.State()
    submit.click(user, [question, chatbot], [question, chatbot], queue=False).then(
        get_answer, inputs=[chatbot], outputs=[chatbot]
    )
    question.submit(user, [question, chatbot], [question, chatbot], queue=False).then(
        get_answer, inputs=[chatbot], outputs=[chatbot]
    )

demo.launch(debug=True, share=False)
