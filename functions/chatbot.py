import os
from openai import OpenAI
from config import Reg,vectorDatabase
from loguru import logger as log
from typing import Optional

def OpenAISetup():
    log.info("INIT OpenAI")
    return OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
    
    )
    
def build_context(documents: list[str],metadatas:Optional[list[dict]] = None):
    
    parts = []
    length = len(documents)
    
    if not metadatas:
        
        for c in range(length):
    
            doc = documents[c]

            parts.append(
                f"{doc}"
            )
                    
        
    else:
        
        for c in range(length):

            meta = metadatas[c]
            doc = documents[c]
            
            print(meta)
            page_data = meta.get("page_numbers", ["?"])
            page = ",".join(str(p) for p in page_data) if isinstance(page_data, list) else page_data
            
            heading = meta.get("headings", "")
            filename = meta.get("file_name","")
            
            
            parts.append(
                f"[Source: page {page}"
                + (f", filename: {filename}")
                + (f", section: {heading}")
                + f"]\n{doc}"
            )
        
    return "\n\n---\n\n".join(parts) 
        
        
        

async def run_ai(msg:str,context:str):
    
    DEFAULT_SYSTEM_PROMPT = """
    You are a factual Q&A assistant that answers STRICTLY and ONLY using the
    provided context (retrieved document chunks). You have no other knowledge
    to draw from.

    ## Core Rules

    1. GROUNDING: Every statement in your answer must be directly traceable to
    the context below. Do not use outside knowledge, assumptions, or
    inference beyond what is explicitly stated.

    2. NO CONTEXT / OUT OF SCOPE: If the answer is not found in the context,
    or the question is unrelated to the provided context, respond with
    EXACTLY this message and nothing else:
    "Maaf, saya hanya bisa menjawab terkait kebijakan internal."
    Do not attempt to guess, generalize, or partially answer in this case.

    3. PARTIAL MATCHES: If the context only partially answers the question,
    answer only the part that is supported, then explicitly state which
    part is not covered by the context (do not fill the gap yourself).

    4. NO FABRICATION: Never invent numbers, names, dates, policies, or
    details not explicitly present in the context. If unsure whether
    something is stated, treat it as NOT stated.

    5. CITATION: Always cite the source chunk/page/section for each claim,
    e.g. [Chunk 2] or [Page 5]. If multiple chunks support a claim, cite
    all of them.

    6. CONFLICTING INFORMATION: If chunks contradict each other, point out
    the conflict explicitly instead of picking one silently.

    7. STYLE: Be concise, direct, and neutral. No speculation, no filler,
    no apologizing beyond the fixed fallback message above.
    """
    
    user_prompt = f"""Context:
    {context}
    
    Question: {msg}
    
    Answer based only on the context above."""

    client = Reg.get('ai',OpenAI)
    
    MODEL = "llama-3.3-70b-versatile"
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    
    return response.choices[0].message.content


async def RagChatbot(msg:str):
    
    vec_db = Reg.get("vec_db",vectorDatabase)
    
    data = vec_db.search(query=msg)
    
    if not data.get('documents'):
        raise ValueError("Data not found")
    
    context = build_context(data['documents'][0],data.get('metadatas')[0])
    
    res = await run_ai(msg,context)
    
    return res