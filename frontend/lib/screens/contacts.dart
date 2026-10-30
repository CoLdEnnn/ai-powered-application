import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data.dart';
import '../ui.dart';

class ContactsScreen extends StatefulWidget {
  const ContactsScreen({super.key});

  @override
  State<ContactsScreen> createState() => _ContactsScreenState();
}

class _ContactsScreenState extends State<ContactsScreen> {
  String _filter = '';

  @override
  Widget build(BuildContext context) {
    final f = _filter.toLowerCase();
    final list = kContacts
        .where((c) => c.name.toLowerCase().contains(f) || c.detail.toLowerCase().contains(f))
        .toList();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Heading('Contacts'),
        TextField(
          decoration: appInput('Filter contacts'),
          onChanged: (v) => setState(() => _filter = v),
        ),
        const SizedBox(height: 16),
        if (list.isEmpty) const Muted('Nothing found.'),
        for (final c in list)
          Block(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(c.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                const SizedBox(height: 2),
                Muted(c.detail),
                const SizedBox(height: 8),
                if (c.room != null) Text('Room: ${c.room}'),
                if (c.phone != null) Text('Phone: ${c.phone}'),
                if (c.email != null)
                  InkWell(
                    onTap: () {
                      Clipboard.setData(ClipboardData(text: c.email!));
                      ScaffoldMessenger.of(context)
                          .showSnackBar(const SnackBar(content: Text('Email copied.')));
                    },
                    child: Text(c.email!, style: const TextStyle(color: kPrimary)),
                  ),
              ],
            ),
          ),
      ],
    );
  }
}
