"""Convert the unified AITU workbook to the starter project's JSONL format.

Place this script in the project root and run:
python prepare_excel_dataset.py --excel "AITU.xlsx"

Uses only the Python standard library. No Excel installation is required.
Outputs are NEW files; existing data and configuration are never overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import hashlib
import json
import math
from pathlib import Path
import posixpath
import random
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

MAIN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def read_xlsx(path):
    """Read cached cell values from XLSX; refuse formulas in the dataset itself."""
    result = {}
    with zipfile.ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            strings = [''.join(e.itertext()) for e in root.findall(f'{MAIN}si')]
        rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        targets = {r.attrib['Id']: r.attrib['Target'] for r in rels}
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        for sheet in book.find(f'{MAIN}sheets'):
            target = targets[sheet.attrib[f'{REL}id']]
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            root = ET.fromstring(archive.read(target))
            rows = {}
            for row in root.findall(f'{MAIN}sheetData/{MAIN}row'):
                cells = {}
                for cell in row.findall(f'{MAIN}c'):
                    address = cell.attrib['r']
                    if sheet.attrib['name'] in {'Dataset', 'Sources', 'Calendars', 'Contacts'} and cell.find(f'{MAIN}f') is not None:
                        raise ValueError(f'Formula in input data: {sheet.attrib["name"]}!{address}. Replace it with a reviewed value first.')
                    column = 0
                    for char in re.match('[A-Z]+', address)[0]:
                        column = column * 26 + ord(char) - 64
                    value = cell.find(f'{MAIN}v')
                    if cell.attrib.get('t') == 'inlineStr':
                        value = ''.join(cell.find(f'{MAIN}is').itertext())
                    elif value is None:
                        value = ''
                    elif cell.attrib.get('t') == 's':
                        value = strings[int(value.text)]
                    else:
                        value = value.text or ''
                    cells[column] = value
                rows[int(row.attrib['r'])] = cells
            result[sheet.attrib['name']] = rows
    return result


def records(sheets, name):
    if name not in sheets:
        raise ValueError(f'Missing sheet: {name}')
    header = sheets[name].get(5, {})
    if not header:
        raise ValueError(f'{name}: expected column headings in Excel row 5.')
    for row_number, cells in sorted(sheets[name].items()):
        if row_number >= 6 and any(str(v).strip() for v in cells.values()):
            yield row_number, {str(title).strip(): str(cells.get(index, '')).strip() for index, title in header.items()}


def normalize(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def date_string(value):
    if not value:
        return 'not stated'
    if re.match(r'^\d{4}-\d{2}-\d{2}', value):
        return value[:10]
    try:
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date().isoformat()
    except (ValueError, OverflowError):
        return value


def urls(text):
    return list(dict.fromkeys(x.rstrip('.,;)') for x in re.findall(r'https?://[^\s|<>]+', text)))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in rows), encoding='utf-8')


def make_context(identifier, question, answer, section, audience, source_ids, source_urls, locator, notes, review, snapshot, row, sheet, workbook):
    return {
        'context_id': 'KB-' + identifier, 'title': section + ' - ' + identifier,
        'text': question + '\n' + answer + ('\nApplicability: ' + notes if notes else ''),
        'audience': audience, 'topic': section, 'source_ids': source_ids,
        'source_urls': source_urls, 'source_locator_en': locator,
        'applicability': notes, 'context_type': 'english_workbook_summary',
        'verification_status': 'team_reviewed' if review.casefold() == 'reviewed' else 'team_review_pending',
        'source_snapshot_date': snapshot, 'team_review': review,
        'origin_locations': [{'workbook': workbook, 'sheet_label_en': sheet, 'row': row}],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--excel', type=Path, required=True)
    parser.add_argument('--name', default='updated', help='New output label; use a new name for each export.')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--reviewed-only', action='store_true', help='Export only Q&As with Team review = Reviewed; otherwise pending labels are preserved.')
    args = parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+', args.name):
        parser.error('--name must contain only letters, digits, underscore or hyphen.')
    project = Path(__file__).resolve().parent
    if not (project / 'training/config.json').is_file() or not (project / 'config.json').is_file():
        raise ValueError('Place this script in the aitu_assistant_starter project root, beside config.json and the training folder.')
    excel = args.excel.resolve()
    out = project / 'data' / args.name
    training_path = project / 'training' / f'config.{args.name}.json'
    app_path = project / f'config.{args.name}.json'
    if out.exists() or training_path.exists() or app_path.exists():
        raise ValueError(f'Output already exists. Choose a fresh label, for example --name updated2. No files were overwritten.')
    sheets = read_xlsx(excel)
    source_catalog, source_lookup = [], {}
    for row, r in records(sheets, 'Sources'):
        sid = r['ID']
        if sid in source_lookup:
            raise ValueError(f'Duplicate source ID: {sid}')
        source = {'source_id': sid, 'title_en': r['Source title'],
                  'urls': urls(r['URL / attachment reference']) or urls(r.get('Evidence / archive link', '')),
                  'reference_type': 'workbook_source_reference',
                  'verification_status': 'team_review_pending',
                  'source_snapshot_date': date_string(r.get('Read / supplied on', '')),
                  'applicability': r['Edition / applicability / limitations'],
                  'origin': {'workbook': excel.name, 'sheet_label_en': 'Sources', 'row': row}}
        source_lookup[sid] = source
        source_catalog.append(source)
    source_ids = sorted(source_lookup, key=len, reverse=True)

    def resolve_sources(reference):
        found = [sid for sid in source_ids if re.search(r'(?<![A-Za-z0-9_-])' + re.escape(sid) + r'(?![A-Za-z0-9_-])', reference)]
        # Do not merge unrelated sources merely because they share an archive link.
        direct = urls(reference)
        if not found:
            found = [s for s in source_ids if any(u in source_lookup[s]['urls'] for u in direct)]
        return sorted(found), list(dict.fromkeys(direct + [u for s in found for u in source_lookup[s]['urls']]))

    qa, excluded = [], []
    seen = set()
    audience_map = {'Applicants': 'applicant', 'Current students': 'current_student', 'Applicants and students': 'shared'}
    for row, r in records(sheets, 'Dataset'):
        rid = r['ID']
        if rid in seen:
            raise ValueError(f'Duplicate Q&A ID: {rid}')
        seen.add(rid)
        review = r.get('Team review', '')
        reason = None
        if normalize(review) == 'needs correction':
            reason = 'Team review = Needs correction'
        elif args.reviewed_only and normalize(review) != 'reviewed':
            reason = 'Not marked Reviewed; --reviewed-only was selected'
        elif not r.get('Question') or not r.get('Answer'):
            reason = 'Missing question or answer'
        elif normalize(review) != 'reviewed' and re.search(r'bank(?:ing)? details|payment details|bank account', r['Question'], re.I):
            reason = 'Unverified payment account details; excluded from operational export'
        if reason:
            excluded.append({'excel_row': row, 'id': rid, 'reason': reason, 'original_record': r})
            continue
        ids, links = resolve_sources(r.get('Source reference', ''))
        if not ids:
            raise ValueError(f'{rid}, Excel row {row}: source reference cannot be resolved in Sources.')
        context = make_context(rid, r['Question'], r['Answer'], r['Section'], audience_map.get(r['Audience'], 'shared'), ids, links,
                               r['Page / section'], r['Applicability / notes'], review, date_string(r['Added / imported on']), row, 'Dataset', excel.name)
        context['source_status'] = r['Status']
        qa.append({'id': 'EN-' + rid, 'question': r['Question'], 'answer': r['Answer'], 'context': context})
    if len(qa) < 10:
        raise ValueError(f'Only {len(qa)} eligible Q&As. Review more records or inspect the selection; no output written.')

    # Keep every source document together. Also group identical / close questions
    # and identical substantial answers across differently named documents.
    parent = list(range(len(qa)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(j)] = find(i)

    owners = {}
    for i, item in enumerate(qa):
        for sid in item['context']['source_ids']:
            if sid in owners:
                union(i, owners[sid])
            else:
                owners[sid] = i
    normalized = [(normalize(x['question']), normalize(x['answer'])) for x in qa]
    for i, (q, a) in enumerate(normalized):
        for j in range(i):
            q2, a2 = normalized[j]
            if q == q2 or (len(a) >= 80 and a == a2) or (min(len(q), len(q2)) >= 35 and SequenceMatcher(None, q, q2).ratio() >= 0.88):
                union(i, j)
    groups = defaultdict(list)
    for i in range(len(qa)):
        groups[find(i)].append(i)
    if len(groups) < 3:
        raise ValueError('Fewer than three independent source/question groups. Review grouping before splitting.')
    rng = random.Random(args.seed)
    group_list = list(groups.values())
    rng.shuffle(group_list)
    group_list.sort(key=len, reverse=True)
    targets = {'train': len(qa) * .8, 'validation': len(qa) * .1, 'test': len(qa) * .1}
    counts = Counter()
    split_rows = {key: [] for key in targets}
    system = (project / 'data/system_prompt.txt').read_text(encoding='utf-8-sig').strip()
    # Reuse the exact prompt implementation used by the local application.
    sys.path.insert(0, str(project))
    from app.prompting import make_messages
    corpus = []
    for group in group_list:
        # Greedy target balancing with whole groups; ratios are approximate.
        split = min(targets, key=lambda s: sum(((counts[t] + (len(group) if t == s else 0)) - targets[t]) ** 2 / max(targets[t], 1) for t in targets))
        ids = sorted(qa[i]['id'] for i in group)
        family = 'FAMILY-' + hashlib.sha256('\n'.join(ids).encode()).hexdigest()[:12]
        for i in group:
            item = qa[i]
            context = item['context']
            context['source_family_id'] = family
            context['supervised_family_split'] = split
            corpus.append(context)
            answer = item['answer']
            # Applicability is part of the supervised answer as well as evidence.
            if context['applicability'] and context['applicability'] not in answer:
                answer += '\nApplicability: ' + context['applicability']
            answer += ' [' + context['context_id'] + ']'
            messages = make_messages(system, item['question'], [context])
            messages.append({'role': 'assistant', 'content': answer})
            split_rows[split].append({'id': item['id'], 'messages': messages, 'metadata': {
                'split': split, 'audience': context['audience'], 'topic': context['topic'], 'behavior': 'answer',
                'construction': 'english_workbook_qa_with_own_evidence', 'context_ids': [context['context_id']],
                'parent_origin_ids': [context['context_id'][3:]], 'source_ids': context['source_ids'],
                'source_family_id': family, 'verification_status': context['verification_status'],
                'source_snapshot_date': context['source_snapshot_date'], 'excel_row': context['origin_locations'][0]['row']}})
        counts[split] += len(group)
    if any(not v for v in split_rows.values()):
        raise ValueError('Whole-group balancing produced an empty split; inspect source groups before training.')

    # Calendar and contact tables remain retrieval-only. Unknown dates stay unknown.
    for sheet in ['Calendars', 'Contacts']:
        for row, r in records(sheets, sheet):
            review = r.get('Team review', '')
            if normalize(review) == 'needs correction' or (args.reviewed_only and normalize(review) != 'reviewed'):
                excluded.append({'excel_row': row, 'sheet': sheet, 'reason': 'Review filter', 'original_record': r})
                continue
            if sheet == 'Calendars':
                identifier = r['ID']
                title = f"{r['Event']} - {r['Degree level']}, {r['Cohort / intake']}, {r['Academic year']}"
                text = f"Start: {date_string(r['Start date'])}. End: {date_string(r['End date'])}."
                notes, locator = r['Applicability / discrepancy'], r['PDF page / row']
            else:
                identifier = f'CONTACT-{row - 5:03}'
                title = r['Service']
                text = '; '.join(f'{k}: {r[k]}' for k in ['Contact / person', 'Email', 'Phone', 'Room', 'Scope / location'] if r[k])
                notes, locator = r['Applicability'], f'Contacts, Excel row {row}'
            ids, links = resolve_sources(r['Source reference'])
            c = make_context(identifier, title, text, sheet, 'current_student', ids, links, locator, notes, review, 'not stated', row, sheet, excel.name)
            c['supervised_family_split'] = 'retrieval_only'
            corpus.append(c)

    for values in split_rows.values():
        values.sort(key=lambda r: r['id'])
    corpus.sort(key=lambda r: r['context_id'])
    assert len({r['context_id'] for r in corpus}) == len(corpus)
    for a, b in [('train', 'validation'), ('train', 'test'), ('validation', 'test')]:
        assert not ({r['metadata']['source_family_id'] for r in split_rows[a]} & {r['metadata']['source_family_id'] for r in split_rows[b]})
    training = json.loads((project / 'training/config.json').read_text(encoding='utf-8-sig'))
    training.update(train_file=f'data/{args.name}/train.jsonl', validation_file=f'data/{args.name}/validation.jsonl', output_dir=f'runs/aitu_lora_{args.name}')
    app = json.loads((project / 'config.json').read_text(encoding='utf-8-sig'))
    app.update(corpus_path=f'data/{args.name}/rag_corpus_en.jsonl', source_catalog_path=f'data/{args.name}/source_catalog_en.json', index_dir=f'index/{args.name}')
    manifest = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'input_file': excel.name,
                'input_sha256': hashlib.sha256(excel.read_bytes()).hexdigest(), 'input_qa': len(seen),
                'eligible_qa': len(qa), 'splits': dict(counts), 'retrieval_contexts': len(corpus),
                'excluded_records': len(excluded), 'reviewed_only': args.reviewed_only,
                'unreviewed_supervised_examples': sum(x['context']['verification_status'] != 'team_reviewed' for x in qa),
                'source_question_groups': len(groups), 'seed': args.seed,
                'limitations': ['Workbook summaries are evidence, not verbatim official sources.',
                                'Conversion does not verify source accuracy or mark records Reviewed.',
                                'Whole source groups and close questions stay together; manually review semantic leakage.',
                                'Splits are approximate 80/10/10; no synthetic claims of collected student data.',
                                'No new unanswerable/clarification examples were invented by this converter.',
                                'Corpus includes evidence for held-out questions; reference answers are excluded from training.',
                                'No tokenizer truncation is performed; run training preflight before any GPU run.']}
    out.mkdir(parents=True)
    for split, values in split_rows.items():
        write_jsonl(out / f'{split}.jsonl', values)
    write_jsonl(out / 'rag_corpus_en.jsonl', corpus)
    write_json(out / 'source_catalog_en.json', source_catalog)
    write_jsonl(out / 'excluded_records.jsonl', excluded)
    write_json(out / 'dataset_manifest.json', manifest)
    test = split_rows['test']
    write_jsonl(out / 'test_prompts.jsonl', [{**r, 'messages': r['messages'][:2]} for r in test])
    write_jsonl(out / 'retrieval_test.jsonl', [{'id': r['id'], 'question': r['messages'][1]['content'].rpartition('\nQUESTION\n')[2],
        'audience': r['metadata']['audience'], 'expected_context_ids': r['metadata']['context_ids'],
        'expected_behavior': r['metadata']['behavior'], 'source_ids': r['metadata']['source_ids']} for r in test])
    write_json(training_path, training)
    write_json(app_path, app)
    print(json.dumps(manifest, indent=2))
    print('\nNext:')
    print(fr'.\.venv-training\Scripts\python.exe training/train_lora.py --config training/config.{args.name}.json --preflight-only')
    print(fr'.\.venv-training\Scripts\python.exe training/train_lora.py --config training/config.{args.name}.json --output-dir runs/smoke_{args.name} --max-steps 2')
    print(fr'.\.venv-training\Scripts\python.exe training/train_lora.py --config training/config.{args.name}.json')
    print('\nFor the updated retrieval corpus, separately build its index:')
    print(fr'.\.venv\Scripts\python.exe scripts/build_index.py --config config.{args.name}.json')
    if manifest['unreviewed_supervised_examples']:
        print('\nNOTICE: pending team-review labels remain pending. This export is draft data, not a verified dataset.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
