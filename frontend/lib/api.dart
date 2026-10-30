import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

/// Talks to the FastAPI backend:
///   GET  /api/health
///   POST /api/chat   {"question": "...", "audience": "all|applicant|current_student"}
class ApiClient {
  ApiClient({required this.baseUrl, this.mock = false});

  /// Example: http://127.0.0.1:8000 . Empty string = same origin as the page.
  String baseUrl;

  /// Demo mode without a backend (flutter run --dart-define=MOCK=true).
  final bool mock;

  Uri _uri(String path) {
    if (baseUrl.trim().isEmpty) return Uri.base.resolve(path);
    final base = baseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    return Uri.parse('$base$path');
  }

  Future<Health> health() async {
    if (mock) {
      return Health(
        status: 'ready',
        modelVariant: 'demo (mock)',
        evidenceStatus: 'pending_team_review',
        snapshotDate: '2026-10-21',
        conversationMode: 'independent_questions',
      );
    }
    try {
      final r = await http.get(_uri('/api/health')).timeout(const Duration(seconds: 10));
      if (r.statusCode != 200) {
        throw ApiException('Server answered ${r.statusCode}.');
      }
      return Health.fromJson(jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>);
    } on ApiException {
      rethrow;
    } catch (_) {
      throw ApiException('Cannot reach the assistant at ${baseUrl.isEmpty ? 'this site' : baseUrl}.');
    }
  }

  Future<ChatAnswer> ask(String question, String audience) async {
    if (mock) return _mockAnswer(question);
    final http.Response r;
    try {
      r = await http
          .post(
            _uri('/api/chat'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'question': question, 'audience': audience}),
          )
          .timeout(const Duration(seconds: 240));
    } catch (_) {
      throw ApiException(
          'Cannot reach the assistant at ${baseUrl.isEmpty ? 'this site' : baseUrl}. Check that the server is running.');
    }
    if (r.statusCode == 200) {
      return ChatAnswer.fromJson(jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>);
    }
    switch (r.statusCode) {
      case 422:
        throw ApiException('The question cannot be processed. Try to rephrase it (2-1200 characters).');
      case 429:
        throw ApiException('The assistant is busy with another question. Try again in a few seconds.');
      case 503:
        throw ApiException('The assistant model is not available right now.');
      default:
        throw ApiException('Unexpected server answer (${r.statusCode}).');
    }
  }

  Future<ChatAnswer> _mockAnswer(String question) async {
    await Future<void>.delayed(const Duration(milliseconds: 1200));
    return ChatAnswer(
      answer:
          'A loan extension is arranged in person at the library, if no other reader has requested the item. [ctx-1]',
      sources: [
        Source(
          contextId: 'ctx-1',
          title: 'Library: borrowing and renewing books',
          text: 'Renewal is arranged during a personal visit to the library if there is no request from other users.',
          urls: ['https://astanait.edu.kz/en/for-students'],
          verificationStatus: 'source_checked_team_review_pending',
          snapshotDate: '2026-10-21',
          score: 0.82,
        ),
      ],
      warnings: [],
      timingSeconds: 1.6,
      usedModel: true,
      modelVariant: 'demo (mock)',
    );
  }
}
