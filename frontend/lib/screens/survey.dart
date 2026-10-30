import 'package:flutter/material.dart';

import '../state.dart';
import '../ui.dart';

class SurveyScreen extends StatefulWidget {
  const SurveyScreen({super.key, required this.question, required this.helpful});
  final String question;
  final bool helpful;

  @override
  State<SurveyScreen> createState() => _SurveyScreenState();
}

class _SurveyScreenState extends State<SurveyScreen> {
  static const _statements = [
    'The answer was easy to understand.',
    'The answer was useful for my question.',
    'I trust the information in this answer.',
  ];

  final Map<int, int> _likert = {};
  String? _correct;

  void _submit() {
    app.addSurvey({
      'question': widget.question,
      'helpful': widget.helpful,
      'likert': Map<int, int>.from(_likert),
      'correct': _correct,
      'time': DateTime.now().toIso8601String(),
    });
    Navigator.of(context).pop();
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Thank you for your feedback.')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Short survey'),
        shape: const Border(bottom: BorderSide(color: kBorder)),
      ),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 600),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Block(
                title: 'Rate this answer',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Muted('Question: ${widget.question}'),
                    const SizedBox(height: 16),
                    for (var i = 0; i < _statements.length; i++) ...[
                      Text(_statements[i], style: const TextStyle(fontWeight: FontWeight.w500)),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Muted('Disagree', size: 12),
                          for (var n = 1; n <= 5; n++)
                            Column(
                              children: [
                                RadioDot(
                                  selected: _likert[i] == n,
                                  onTap: () => setState(() => _likert[i] = n),
                                ),
                                const SizedBox(height: 2),
                                Muted('$n', size: 12),
                              ],
                            ),
                          const Muted('Agree', size: 12),
                        ],
                      ),
                      const SizedBox(height: 16),
                    ],
                    const Text('Was the information correct?', style: TextStyle(fontWeight: FontWeight.w500)),
                    const SizedBox(height: 8),
                    for (final opt in const ['Yes', 'Partly', 'No'])
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: InkWell(
                          onTap: () => setState(() => _correct = opt),
                          child: Row(
                            children: [
                              RadioDot(selected: _correct == opt, onTap: () => setState(() => _correct = opt)),
                              const SizedBox(width: 8),
                              Text(opt),
                            ],
                          ),
                        ),
                      ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        PrimaryButton('Next', onPressed: _submit),
                        const SizedBox(width: 8),
                        OutlineButtonX('Cancel', onPressed: () => Navigator.of(context).pop()),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
