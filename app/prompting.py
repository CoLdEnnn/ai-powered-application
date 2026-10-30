import re


class PromptTooLong(ValueError):
    pass


def make_messages(system: str, question: str, contexts: list[dict], audience: str = 'all') -> list[dict]:
    blocks = []
    for c in contexts:
        blocks.append(
            f"[{c['context_id']}]\n"
            f"Evidence type: English paraphrase of a supplied workbook summary.\n"
            f"Review status: {c.get('verification_status','unknown')}. Snapshot: {c.get('source_snapshot_date','not stated')}.\n"
            f"Source IDs: {', '.join(c.get('source_ids',[]))}.\n"
            f"Source location: {c.get('source_locator_en','not stated')}.\n"
            f"{c['text']}"
        )
    user = 'CONTEXT\n'+'\n\n'.join(blocks)+'\n\nQUESTION\n'+question
    # The filter selects an audience only. It does not establish their degree,
    # cohort, campaign, funding route, or academic year.
    if audience != 'all':
        user = f'User audience: {audience}. Other personal details are not established.\n\n'+user
    return [{'role':'system','content':system},{'role':'user','content':user}]


def fit_prompt(system: str, question: str, contexts: list[dict], *, audience: str, count_tokens, context_size: int, max_new_tokens: int):
    selected = list(contexts)
    while selected:
        messages = make_messages(system,question,selected,audience)
        count = count_tokens(messages)
        if count+max_new_tokens+16 <= context_size:
            return messages,selected,count
        selected.pop()
    raise PromptTooLong('The question and a complete evidence passage do not fit the configured context window. Shorten the question or increase context_size. No evidence was silently truncated.')


def citation_check(answer: str, contexts: list[dict]) -> dict:
    cited = list(dict.fromkeys(re.findall(r'\[(KB-[A-Za-z0-9_-]+)\]',answer)))
    supplied = {c['context_id'] for c in contexts}
    unknown = [cid for cid in cited if cid not in supplied]
    return {'cited_context_ids':cited,'unknown_context_ids':unknown,'has_citation':bool(cited),'all_citations_supplied':not unknown}
