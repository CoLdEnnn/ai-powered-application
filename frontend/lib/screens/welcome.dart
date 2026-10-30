import 'package:flutter/material.dart';

import '../state.dart';
import '../ui.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'AITU Assistant',
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: kPrimary),
                ),
                const SizedBox(height: 16),
                Block(
                  title: 'Welcome',
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Ask a question about studying at Astana IT University. '
                        'The assistant finds the answer in university documents and shows the sources.',
                        style: TextStyle(height: 1.4),
                      ),
                      const SizedBox(height: 16),
                      const Muted('I am a:'),
                      const SizedBox(height: 6),
                      const AudienceDropdown(),
                      const SizedBox(height: 16),
                      const AlertBox(
                        'Answers are generated automatically and can contain mistakes. '
                        'Please check important information in the sources.',
                      ),
                      PrimaryButton('Continue', onPressed: app.start),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
