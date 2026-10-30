import 'package:flutter/material.dart';

import '../data.dart';
import '../shell.dart';
import '../state.dart';
import '../ui.dart';

class TopicsScreen extends StatefulWidget {
  const TopicsScreen({super.key});

  @override
  State<TopicsScreen> createState() => _TopicsScreenState();
}

class _TopicsScreenState extends State<TopicsScreen> {
  String _filter = '';

  @override
  Widget build(BuildContext context) {
    final list = kTopics.where((t) => t.name.toLowerCase().contains(_filter.toLowerCase())).toList();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Heading('Topics'),
        TextField(
          decoration: appInput('Filter topics'),
          onChanged: (v) => setState(() => _filter = v),
        ),
        const SizedBox(height: 16),
        if (list.isEmpty) const Muted('Nothing found.'),
        for (final t in list)
          Block(
            padding: EdgeInsets.zero,
            child: Theme(
              data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                title: Text(t.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: Muted('${t.count} documents in the knowledge base'),
                children: [
                  for (final q in t.questions)
                    ListTile(
                      dense: true,
                      title: Text(q, style: const TextStyle(color: kPrimary)),
                      onTap: () {
                        app.setDraft(q);
                        currentTab.value = 0;
                      },
                    ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
