// Data classes that match the JSON of the AITU backend (FastAPI).

class Source {
  Source({
    required this.contextId,
    required this.title,
    required this.text,
    required this.urls,
    this.verificationStatus,
    this.snapshotDate,
    this.score,
  });

  final String contextId;
  final String title;
  final String text;
  final List<String> urls;
  final String? verificationStatus;
  final String? snapshotDate;
  final double? score;

  factory Source.fromJson(Map<String, dynamic> j) {
    final urls = j['source_urls'];
    return Source(
      contextId: (j['context_id'] ?? '').toString(),
      title: (j['title'] ?? '').toString(),
      text: (j['text'] ?? '').toString(),
      urls: urls is List ? urls.map((e) => e.toString()).toList() : <String>[],
      verificationStatus: j['verification_status']?.toString(),
      snapshotDate: j['source_snapshot_date']?.toString(),
      score: j['score'] is num ? (j['score'] as num).toDouble() : null,
    );
  }
}

class ChatAnswer {
  ChatAnswer({
    required this.answer,
    required this.sources,
    required this.warnings,
    required this.timingSeconds,
    required this.usedModel,
    this.modelVariant,
  });

  final String answer;
  final List<Source> sources;
  final List<String> warnings;
  final double timingSeconds;
  final bool usedModel;
  final String? modelVariant;

  factory ChatAnswer.fromJson(Map<String, dynamic> j) {
    final src = j['sources'];
    final warn = j['warnings'];
    return ChatAnswer(
      answer: (j['answer'] ?? '').toString(),
      sources: src is List
          ? src
              .whereType<Map>()
              .map((e) => Source.fromJson(Map<String, dynamic>.from(e)))
              .toList()
          : <Source>[],
      warnings: warn is List ? warn.map((e) => e.toString()).toList() : <String>[],
      timingSeconds: j['timing_seconds'] is num ? (j['timing_seconds'] as num).toDouble() : 0,
      usedModel: j['used_model'] == true,
      modelVariant: j['model_variant']?.toString(),
    );
  }
}

class Health {
  Health({
    required this.status,
    this.modelVariant,
    this.evidenceStatus,
    this.snapshotDate,
    this.conversationMode,
  });

  final String status; // "ready" or "model_unavailable"
  final String? modelVariant;
  final String? evidenceStatus;
  final String? snapshotDate;
  final String? conversationMode;

  bool get ready => status == 'ready';

  factory Health.fromJson(Map<String, dynamic> j) => Health(
        status: (j['status'] ?? 'unknown').toString(),
        modelVariant: j['model_variant']?.toString(),
        evidenceStatus: j['evidence_status']?.toString(),
        snapshotDate: j['source_snapshot_date']?.toString(),
        conversationMode: j['conversation_mode']?.toString(),
      );
}

/// One question in the chat with its (future) answer.
class ChatItem {
  ChatItem(this.question) : asked = DateTime.now();

  final String question;
  final DateTime asked;
  bool loading = true;
  ChatAnswer? answer;
  String? error;
}

class ApiException implements Exception {
  ApiException(this.message);
  final String message;
  @override
  String toString() => message;
}
