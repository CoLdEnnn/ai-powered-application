import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'state.dart';

// Colors taken from the Figma design (flat, Moodle-like look).
const kPrimary = Color(0xFF0F6CBF);
const kText = Color(0xFF1D2125);
const kMuted = Color(0xFF6A737B);
const kBorder = Color(0xFFCED4DA);
const kBg = Color(0xFFF4F5F7);
const kInfoBg = Color(0xFFE6F1FA);
const kInfoText = Color(0xFF0A4A85);
const kWarnBg = Color(0xFFFFF3CD);
const kWarnText = Color(0xFF856404);
const kDangerBg = Color(0xFFF8D7DA);
const kDangerText = Color(0xFF721C24);

const kRadius = BorderRadius.all(Radius.circular(4));

/// White box with a thin border and an optional title bar.
class Block extends StatelessWidget {
  const Block({
    super.key,
    this.title,
    required this.child,
    this.padding = const EdgeInsets.all(16),
  });

  final String? title;
  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: kBorder),
        borderRadius: kRadius,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (title != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: kBorder)),
              ),
              child: Text(
                title!,
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: kText),
              ),
            ),
          Padding(padding: padding, child: child),
        ],
      ),
    );
  }
}

class Heading extends StatelessWidget {
  const Heading(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Text(
          text,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600, color: kText),
        ),
      );
}

class Muted extends StatelessWidget {
  const Muted(this.text, {super.key, this.size = 13});
  final String text;
  final double size;

  @override
  Widget build(BuildContext context) =>
      Text(text, style: TextStyle(fontSize: size, color: kMuted, height: 1.4));
}

enum AlertKind { info, warn, danger }

class AlertBox extends StatelessWidget {
  const AlertBox(this.text, {super.key, this.kind = AlertKind.info});
  final String text;
  final AlertKind kind;

  @override
  Widget build(BuildContext context) {
    final Color bg;
    final Color fg;
    switch (kind) {
      case AlertKind.info:
        bg = kInfoBg;
        fg = kInfoText;
        break;
      case AlertKind.warn:
        bg = kWarnBg;
        fg = kWarnText;
        break;
      case AlertKind.danger:
        bg = kDangerBg;
        fg = kDangerText;
        break;
    }
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: bg, borderRadius: kRadius),
      child: Text(text, style: TextStyle(color: fg, fontSize: 14, height: 1.4)),
    );
  }
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton(this.label, {super.key, required this.onPressed});
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: onPressed,
      style: ElevatedButton.styleFrom(
        backgroundColor: kPrimary,
        foregroundColor: Colors.white,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: const RoundedRectangleBorder(borderRadius: kRadius),
      ),
      child: Text(label),
    );
  }
}

class OutlineButtonX extends StatelessWidget {
  const OutlineButtonX(this.label, {super.key, required this.onPressed});
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: kPrimary,
        side: const BorderSide(color: kPrimary),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: const RoundedRectangleBorder(borderRadius: kRadius),
      ),
      child: Text(label),
    );
  }
}

InputDecoration appInput(String hint) {
  const border = OutlineInputBorder(borderRadius: kRadius, borderSide: BorderSide(color: kBorder));
  return const InputDecoration(
    isDense: true,
    filled: true,
    fillColor: Colors.white,
    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 14),
    border: border,
    enabledBorder: border,
    focusedBorder: OutlineInputBorder(borderRadius: kRadius, borderSide: BorderSide(color: kPrimary)),
    counterText: '',
  ).copyWith(hintText: hint);
}

class RadioDot extends StatelessWidget {
  const RadioDot({super.key, required this.selected, required this.onTap});
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 22,
        height: 22,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: Colors.white,
          border: Border.all(color: selected ? kPrimary : kBorder, width: 2),
        ),
        alignment: Alignment.center,
        child: selected
            ? Container(
                width: 10,
                height: 10,
                decoration: const BoxDecoration(shape: BoxShape.circle, color: kPrimary),
              )
            : null,
      ),
    );
  }
}

/// Clickable text that opens a link in a new tab / browser.
class LinkText extends StatelessWidget {
  const LinkText(this.url, {super.key, this.label});
  final String url;
  final String? label;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () async {
        final uri = Uri.tryParse(url);
        if (uri == null) return;
        try {
          await launchUrl(uri, mode: LaunchMode.externalApplication);
        } catch (_) {}
      },
      child: Text(
        label ?? url,
        style: const TextStyle(color: kPrimary, decoration: TextDecoration.underline, fontSize: 13),
      ),
    );
  }
}

const audienceLabels = <String, String>{
  'all': 'General (all)',
  'applicant': 'Applicant',
  'current_student': 'Current student',
};

class AudienceDropdown extends StatelessWidget {
  const AudienceDropdown({super.key});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: kBorder),
          borderRadius: kRadius,
        ),
        child: DropdownButtonHideUnderline(
          child: DropdownButton<String>(
            isExpanded: true,
            value: app.audience,
            items: [
              for (final e in audienceLabels.entries)
                DropdownMenuItem<String>(value: e.key, child: Text(e.value)),
            ],
            onChanged: (v) {
              if (v != null) app.setAudience(v);
            },
          ),
        ),
      ),
    );
  }
}
