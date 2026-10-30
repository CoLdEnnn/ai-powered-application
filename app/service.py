import threading
import time
from .prompting import fit_prompt,citation_check


class AssistantBusy(RuntimeError):
    pass


class AssistantService:
    def __init__(self, settings, retriever, model):
        self.settings,self.retriever,self.model=settings,retriever,model
        self.system=settings.system_prompt_path.read_text(encoding='utf-8').strip()
        self.lock=threading.Lock()

    def ask(self, question: str, audience: str = 'all') -> dict:
        if not self.lock.acquire(blocking=False):
            raise AssistantBusy('The local model is answering another question. Try again when it finishes.')
        started=time.perf_counter()
        try:
            hits=self.retriever.search(question,audience=audience,top_k=self.settings.retrieval_k,min_similarity=self.settings.min_similarity)
            if not hits:
                return {'answer':'I could not find a matching passage in the selected evidence. Please specify the topic, degree level and academic year, or check the relevant university source.','sources':[],'citation_status':{},'warnings':['No matching evidence was supplied to the model.'],'model_variant':self.settings.model_variant,'timing_seconds':round(time.perf_counter()-started,3),'used_model':False}
            messages,selected,input_count=fit_prompt(self.system,question,hits,audience=audience,count_tokens=self.model.count_tokens,context_size=self.settings.context_size,max_new_tokens=self.settings.max_new_tokens)
            result=self.model.complete(messages,max_tokens=self.settings.max_new_tokens,temperature=self.settings.temperature,top_p=self.settings.top_p,seed=self.settings.seed)
            citations=citation_check(result['answer'],selected)
            warnings=[]
            if citations['unknown_context_ids']:
                warnings.append('The answer contains an evidence ID that was not supplied. Treat its source attribution as unverified.')
            if not citations['has_citation']:
                warnings.append('The answer has no evidence citation. The passages below were retrieved, not confirmed as supporting every claim.')
            if result.get('finish_reason')=='length':
                warnings.append('The response reached the output limit and may be incomplete.')
            if len(selected)<len(hits):
                warnings.append('Lower-ranked passages were omitted to fit the model context window; retained passages are complete.')
            sources=[]
            for c in selected:
                sources.append({k:c.get(k) for k in ('context_id','title','text','audience','source_ids','source_urls','source_locator_en','applicability','source_snapshot_date','verification_status','origin_locations','review_notes','score')})
            return {'answer':result['answer'],'sources':sources,'citation_status':citations,'warnings':warnings,'model_variant':self.settings.model_variant,'timing_seconds':round(time.perf_counter()-started,3),'input_tokens':input_count,'usage':result.get('usage',{}),'used_model':True}
        finally:
            self.lock.release()

    def close(self):
        self.model.close()
