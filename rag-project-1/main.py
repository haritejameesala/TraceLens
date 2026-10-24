import os, httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tracelens_sdk import TraceLens
API=os.getenv("TRACELENS_API_URL","http://127.0.0.1:8000")
QUESTION="What is the minimum password length?"
DOCS=[
 {"id":"security-01","text":"Company passwords must be at least 14 characters long."},
 {"id":"security-02","text":"Remote access requires multi-factor authentication."},
 {"id":"security-03","text":"Employees must never share passwords with colleagues."},
]
def retrieve(question, broken=False):
 vectorizer=TfidfVectorizer()
 matrix=vectorizer.fit_transform([d["text"] for d in DOCS]+[question])
 scores=cosine_similarity(matrix[-1],matrix[:-1]).ravel()
 ranked=sorted(zip(scores,DOCS),key=lambda x:x[0],reverse=True)
 results=[d for score,d in ranked if score>0.05][:2]
 return [] if broken else results
def answer(docs):
 return docs[0]["text"] if docs else "No relevant evidence was retrieved."
def main():
 with httpx.Client(base_url=API,timeout=10) as c:
  c.get("/health").raise_for_status()
  r=c.post("/api/projects",json={"name":"RAG Project 1 - TF-IDF","description":"Standalone TF-IDF RAG","framework":"custom-python-tfidf"})
  r.raise_for_status(); project_id=r.json()["project_id"]
 def execute(tracer,name,version,broken,baseline=None):
  with tracer.start_run(name,version=version,baseline_run_id=baseline,metadata={"project":"rag-project-1","retriever":"tfidf"}) as run:
   rp={"query":QUESTION,"retriever":"tfidf","version":version}
   with run.trace_step("retrieve_documents",event_type="retrieval",payload=rp):
    docs=retrieve(QUESTION,broken)
    rp.update({"relevant_chunk_count":len(docs),"chunk_ids":[d["id"] for d in docs]})
   gp={}
   with run.trace_step("generate_answer",event_type="generation",payload=gp):
    result=answer(docs); gp.update({"answer_supported":bool(docs),"output_summary":result[:160]})
   print(name+": "+result); return run.run_id
 with TraceLens(project_id,api_url=API,strict=True) as tracer:
  baseline=execute(tracer,"baseline-success","tfidf-v1",False)
  current=execute(tracer,"retrieval-regression","tfidf-v2-buggy-filter",True,baseline)
 with httpx.Client(base_url=API,timeout=10) as c:
  r=c.post("/api/runs/compare",json={"baseline_run_id":baseline,"current_run_id":current}); r.raise_for_status()
  print("TraceLens comparison:",r.text)
 print("Project:",project_id,"Baseline:",baseline,"Current:",current)
if __name__=="__main__": main()
