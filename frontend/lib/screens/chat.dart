import 'package:flutter/material.dart';

import '../data.dart';
import '../models.dart';
import '../state.dart';
import '../ui.dart';
import 'survey.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _ctrl = TextEditingController();
  final _scroll = ScrollController();
  String _lastSig = '';

  @override
  void initState() {
    super.initState();
    app.addListener(_onApp);
  }

  @override
  void dispose() {
    app.removeListener(_onApp);
    _ctrl.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _onApp() {
    final d = app.draft;
    if (d != null) {
      app.draft = null;
      _ctrl.text = d;
      _ctrl.selection = TextSelection.collapsed(offset: d.length);
    }
    final sig = '${app.items.length}-${app.busy}';
    if (sig != _lastSig) {
      _lastSig = sig;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) {
          _scroll.animateTo(
            _scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOut,
          );
        }
      });
    }
  }

  void _send(String text) {
    final q = text.trim();
    if (q.length < 2) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Please type a longer question (at least 2 characters).')));
      return;
    }
    if (app.busy) return;
    _ctrl.clear();
    app.ask(q);
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        return Column(
          children: [
            Expanded(
              child: ListView(
                controller: _scroll,
                padding: const EdgeInsets.all(16),
                children: [
                  if (app.items.isEmpty) _home(),
                  for (final item in app.items) ...[
                    _QuestionPost(item: item),
                    _AnswerPost(item: item, onRetry: () => _send(item.question)),
                  ],
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(top: BorderSide(color: kBorder)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _ctrl,
                      enabled: !app.busy,
                      maxLength: 1200,
                      textInputAction: TextInputAction.send,
                      onSubmitted: _send,
                      decoration: appInput('Type your question...'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  PrimaryButton('Ask', onPressed: app.busy ? null : () => _send(_ctrl.text)),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _home() {
    return Block(
      title: 'Ask a question',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const AlertBox(
            'Ask about certificates, the academic calendar, services, programs or tuition. '
            'Each question is answered on its own: the assistant does not remember earlier questions.',
          ),
          const Text('Common questions', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          for (final q in kCommonQuestions)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: InkWell(
                onTap: () => _send(q),
                child: Text(q, style: const TextStyle(color: kPrimary, fontSize: 14)),
              ),
            ),
        ],
      ),
    );
  }
}

class _QuestionPost extends StatelessWidget {
  const _QuestionPost({required this.item});
  final ChatItem item;

  @override
  Widget build(BuildContext context) {
    return Block(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Muted('Your question', size: 12),
          const SizedBox(height: 4),
          SelectableText(item.question, style: const TextStyle(fontSize: 15, height: 1.4)),
        ],
      ),
    );
  }
}

class _AnswerPost extends StatelessWidget {
  const _AnswerPost({required this.item, required this.onRetry});
  final ChatItem item;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    if (item.loading) {
      return const Block(
        title: 'Answer',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            LinearProgressIndicator(color: kPrimary, backgroundColor: kInfoBg),
            SizedBox(height: 12),
            Muted('Looking for the answer. On a slow computer this can take a minute or more.'),
          ],
        ),
      );
    }
    if (item.error != null) {
      return Block(
        title: 'Answer',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AlertBox(item.error!, kind: AlertKind.danger),
            OutlineButtonX('Try again', onPressed: onRetry),
          ],
        ),
      );
    }
    final a = item.answer!;
    return Block(
      title: 'Answer',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SelectableText(a.answer, style: const TextStyle(fontSize: 15, height: 1.5)),
          const SizedBox(height: 12),
          for (final w in a.warnings) AlertBox(w, kind: AlertKind.warn),
          if (app.showTime)
            Muted('Response time: ${a.timingSeconds.toStringAsFixed(1)} s'
                '${a.modelVariant != null ? '  |  model: ${a.modelVariant}' : ''}'),
          if (app.showSources && a.sources.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('Sources', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            for (final s in a.sources) _SourceTile(source: s),
          ],
          const SizedBox(height: 8),
          const Divider(),
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              const Muted('Was this answer helpful?'),
              TextButton(
                onPressed: () => _openSurvey(context, true),
                child: const Text('Yes'),
              ),
              TextButton(
                onPressed: () => _openSurvey(context, false),
                child: const Text('No'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _openSurvey(BuildContext context, bool helpful) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => SurveyScreen(question: item.question, helpful: helpful)),
    );
  }
}

class _SourceTile extends StatelessWidget {
  const _SourceTile({required this.source});
  final Source source;

  @override
  Widget build(BuildContext context) {
    final meta = <String>[
      if (source.verificationStatus != null) 'Verification: ${source.verificationStatus}',
      if (source.snapshotDate != null) 'Snapshot: ${source.snapshotDate}',
    ].join('  |  ');
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: kBg,
        border: Border.all(color: kBorder),
        borderRadius: kRadius,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('[${source.contextId}] ${source.title}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          if (source.text.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(source.text, maxLines: 4, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13, height: 1.4)),
          ],
          for (final u in source.urls)
            Padding(padding: const EdgeInsets.only(top: 4), child: LinkText(u)),
          if (meta.isNotEmpty) ...[
            const SizedBox(height: 4),
            Muted(meta, size: 12),
          ],
        ],
      ),
    );
  }
}
