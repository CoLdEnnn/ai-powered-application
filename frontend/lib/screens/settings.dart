import 'package:flutter/material.dart';

import '../state.dart';
import '../ui.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _url = TextEditingController(text: app.api.baseUrl);

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  Widget _row(String k, String? v) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 150, child: Muted(k)),
            Expanded(child: Text(v ?? '-', style: const TextStyle(fontSize: 14))),
          ],
        ),
      );

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final h = app.health;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Heading('Settings'),
            Block(
              title: 'Connection',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (app.api.mock) const AlertBox('Demo mode is on (MOCK=true). Answers are fake.', kind: AlertKind.warn),
                  const Muted('Backend address'),
                  const SizedBox(height: 6),
                  TextField(controller: _url, decoration: appInput('http://127.0.0.1:8000')),
                  const SizedBox(height: 4),
                  const Muted('Leave empty if the site is served by the backend itself.', size: 12),
                  const SizedBox(height: 12),
                  PrimaryButton('Save and check', onPressed: () => app.setBaseUrl(_url.text)),
                ],
              ),
            ),
            Block(
              title: 'Server status',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (app.healthError != null) AlertBox(app.healthError!, kind: AlertKind.danger),
                  if (h != null) ...[
                    _row('Status', h.status),
                    _row('Model', h.modelVariant),
                    _row('Evidence status', h.evidenceStatus),
                    _row('Source snapshot', h.snapshotDate),
                    _row('Conversation mode', h.conversationMode),
                  ],
                  if (h == null && app.healthError == null) const Muted('Checking...'),
                  const SizedBox(height: 8),
                  OutlineButtonX('Check again', onPressed: app.loadHealth),
                ],
              ),
            ),
            Block(
              title: 'Preferences',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Muted('I am a:'),
                  const SizedBox(height: 6),
                  const AudienceDropdown(),
                  const SizedBox(height: 8),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    activeColor: kPrimary,
                    title: const Text('Show sources'),
                    value: app.showSources,
                    onChanged: (v) => app.setShowSources(v ?? true),
                  ),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    activeColor: kPrimary,
                    title: const Text('Show response time'),
                    value: app.showTime,
                    onChanged: (v) => app.setShowTime(v ?? true),
                  ),
                ],
              ),
            ),
            const Block(
              title: 'About',
              child: Muted(
                'Model, retrieval and generation settings are part of the server config (config.json) '
                'and cannot be changed from this app. Language: English.',
              ),
            ),
          ],
        );
      },
    );
  }
}
