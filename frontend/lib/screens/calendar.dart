import 'package:flutter/material.dart';

import '../data.dart';
import '../ui.dart';

class CalendarScreen extends StatelessWidget {
  const CalendarScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    Period? current;
    Period? next;
    for (final p in kPeriods) {
      if (!today.isBefore(p.start) && !today.isAfter(p.end)) current = p;
      if (next == null && p.start.isAfter(today)) next = p;
    }

    String status(Period p) {
      if (p == current) return 'Now';
      if (p.end.isBefore(today)) return 'Finished';
      return 'Upcoming';
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Heading('Academic calendar'),
        const Muted('Year 2, bachelor, academic year 2026-27.'),
        const SizedBox(height: 12),
        if (current != null)
          AlertBox('Now: ${current.name}. ${current.end.difference(today).inDays} days left (until ${fmtDate(current.end)}).')
        else if (next != null)
          AlertBox('Next: ${next.name} starts on ${fmtDate(next.start)} '
              '(in ${next.start.difference(today).inDays} days).')
        else
          const AlertBox('The academic year is over.'),
        Block(
          title: 'Periods',
          padding: EdgeInsets.zero,
          child: Column(
            children: [
              for (final p in kPeriods)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: p == current ? kInfoBg : null,
                    border: const Border(bottom: BorderSide(color: kBorder)),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(p.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                            const SizedBox(height: 2),
                            Muted('${fmtDate(p.start)}  to  ${fmtDate(p.end)}'),
                          ],
                        ),
                      ),
                      Text(
                        status(p),
                        style: TextStyle(
                          color: p == current ? kPrimary : kMuted,
                          fontWeight: p == current ? FontWeight.w600 : FontWeight.w400,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
        const Muted('Dates are taken from the knowledge base snapshot. Always check the official calendar.'),
      ],
    );
  }
}
