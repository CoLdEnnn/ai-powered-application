import 'package:flutter/material.dart';

import '../data.dart';
import '../shell.dart';
import '../state.dart';
import '../ui.dart';

/// The exact dates depend on the programme and cohort, so this screen does not
/// show a fixed date table. It explains the structure and sends calendar
/// questions to the assistant, which answers from the checked sources.
class CalendarScreen extends StatelessWidget {
  const CalendarScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Heading('Academic calendar'),
        const AlertBox(
          'According to Academic Policy (Edition 4), an AITU academic year has three trimesters. '
          'Exact dates depend on your programme and cohort, so check the official calendar for your group.',
        ),
        Block(
          title: 'Ask about the calendar and academic rules',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Muted('Tap a question to open it in the chat.'),
              const SizedBox(height: 10),
              for (final q in kCalendarQuestions)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: InkWell(
                    onTap: () {
                      app.setDraft(q);
                      currentTab.value = 0;
                    },
                    child: Text(q, style: const TextStyle(color: kPrimary, fontSize: 14, height: 1.3)),
                  ),
                ),
            ],
          ),
        ),
        const Muted('The assistant answers from a checked set of university documents. Source review is not finished yet.'),
      ],
    );
  }
}
