import 'package:flutter/material.dart';

import 'screens/calendar.dart';
import 'screens/chat.dart';
import 'screens/contacts.dart';
import 'screens/settings.dart';
import 'screens/topics.dart';
import 'state.dart';
import 'ui.dart';

/// Index of the open tab (0 chat, 1 topics, 2 calendar, 3 contacts, 4 settings).
final ValueNotifier<int> currentTab = ValueNotifier<int>(0);

const _labels = ['Chat', 'Topics', 'Calendar', 'Contacts', 'Settings'];
const _icons = [
  Icons.chat_bubble_outline,
  Icons.list_alt,
  Icons.calendar_today_outlined,
  Icons.contacts_outlined,
  Icons.settings_outlined,
];

class AppShell extends StatelessWidget {
  const AppShell({super.key});

  static const _pages = <Widget>[
    ChatScreen(),
    TopicsScreen(),
    CalendarScreen(),
    ContactsScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<int>(
      valueListenable: currentTab,
      builder: (context, index, _) {
        return LayoutBuilder(builder: (context, c) {
          final wide = c.maxWidth >= 800;
          final body = IndexedStack(index: index, children: _pages);
          if (wide) {
            return Scaffold(
              body: Column(
                children: [
                  Container(
                    height: 56,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      border: Border(bottom: BorderSide(color: kBorder)),
                    ),
                    child: const Row(
                      children: [
                        Text(
                          'AITU Assistant',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: kPrimary),
                        ),
                        Spacer(),
                        StatusBadge(compact: false),
                      ],
                    ),
                  ),
                  Expanded(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          width: 270,
                          child: SingleChildScrollView(
                            padding: const EdgeInsets.all(16),
                            child: _SideNav(index: index),
                          ),
                        ),
                        Expanded(
                          child: Align(
                            alignment: Alignment.topCenter,
                            child: ConstrainedBox(
                              constraints: const BoxConstraints(maxWidth: 900),
                              child: body,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }
          return Scaffold(
            appBar: AppBar(
              title: const Text('AITU Assistant', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: kPrimary)),
              actions: const [
                Padding(padding: EdgeInsets.only(right: 16), child: Center(child: StatusBadge(compact: true))),
              ],
              shape: const Border(bottom: BorderSide(color: kBorder)),
            ),
            body: body,
            bottomNavigationBar: BottomNavigationBar(
              type: BottomNavigationBarType.fixed,
              currentIndex: index,
              selectedItemColor: kPrimary,
              unselectedItemColor: kMuted,
              backgroundColor: Colors.white,
              selectedFontSize: 12,
              unselectedFontSize: 12,
              onTap: (i) => currentTab.value = i,
              items: [
                for (var i = 0; i < _labels.length; i++)
                  BottomNavigationBarItem(icon: Icon(_icons[i]), label: _labels[i]),
              ],
            ),
          );
        });
      },
    );
  }
}

class _SideNav extends StatelessWidget {
  const _SideNav({required this.index});
  final int index;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Block(
          title: 'Navigation',
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            children: [
              for (var i = 0; i < _labels.length; i++)
                InkWell(
                  onTap: () => currentTab.value = i,
                  child: Container(
                    width: double.infinity,
                    color: i == index ? kInfoBg : null,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    child: Row(
                      children: [
                        Icon(_icons[i], size: 18, color: i == index ? kPrimary : kMuted),
                        const SizedBox(width: 10),
                        Text(
                          _labels[i],
                          style: TextStyle(
                            color: i == index ? kPrimary : kText,
                            fontWeight: i == index ? FontWeight.w600 : FontWeight.w400,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
        ListenableBuilder(
          listenable: app,
          builder: (context, _) => Block(
            title: 'Recent questions',
            child: app.items.isEmpty
                ? const Muted('No questions yet.')
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final it in app.items.reversed.take(8))
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: InkWell(
                            onTap: () {
                              app.setDraft(it.question);
                              currentTab.value = 0;
                            },
                            child: Text(
                              it.question,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(color: kPrimary, fontSize: 13),
                            ),
                          ),
                        ),
                    ],
                  ),
          ),
        ),
      ],
    );
  }
}

/// Small server status indicator + language label.
class StatusBadge extends StatelessWidget {
  const StatusBadge({super.key, required this.compact});
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final Color color;
        final String text;
        if (app.health?.ready == true) {
          color = const Color(0xFF2E9E4F);
          text = 'Assistant ready';
        } else if (app.healthError != null) {
          color = const Color(0xFFC0392B);
          text = 'Offline';
        } else if (app.health != null) {
          color = const Color(0xFFE0A100);
          text = 'Model unavailable';
        } else {
          color = kMuted;
          text = 'Checking...';
        }
        final dot = Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(shape: BoxShape.circle, color: color),
        );
        if (compact) {
          return Tooltip(message: text, child: dot);
        }
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            dot,
            const SizedBox(width: 6),
            Text(text, style: const TextStyle(fontSize: 13, color: kMuted)),
            const SizedBox(width: 16),
            const Text('English (en)', style: TextStyle(fontSize: 13, color: kMuted)),
          ],
        );
      },
    );
  }
}
