import 'package:flutter/foundation.dart';

import 'api.dart';
import 'models.dart';

/// Very simple app state (one global object, no extra packages).
class AppState extends ChangeNotifier {
  AppState()
      : api = ApiClient(
          // Change with: --dart-define=API_BASE=http://192.168.0.10:8000
          baseUrl: const String.fromEnvironment('API_BASE', defaultValue: 'http://127.0.0.1:8000'),
          mock: const bool.fromEnvironment('MOCK'),
        );

  ApiClient api;
  bool started = false;

  /// "all", "applicant" or "current_student" (matches the backend).
  String audience = 'all';
  bool showSources = true;
  bool showTime = true;

  final List<ChatItem> items = [];
  Health? health;
  String? healthError;

  /// Text that should appear in the input field (set by Topics / history links).
  String? draft;

  final List<Map<String, dynamic>> surveys = [];

  bool get busy => items.isNotEmpty && items.last.loading;

  void start() {
    started = true;
    notifyListeners();
    loadHealth();
  }

  void setAudience(String value) {
    audience = value;
    notifyListeners();
  }

  void setShowSources(bool v) {
    showSources = v;
    notifyListeners();
  }

  void setShowTime(bool v) {
    showTime = v;
    notifyListeners();
  }

  void setDraft(String text) {
    draft = text;
    notifyListeners();
  }

  Future<void> setBaseUrl(String url) async {
    api.baseUrl = url;
    await loadHealth();
  }

  Future<void> loadHealth() async {
    try {
      health = await api.health();
      healthError = null;
    } catch (e) {
      health = null;
      healthError = e.toString();
    }
    notifyListeners();
  }

  Future<void> ask(String question) async {
    final item = ChatItem(question);
    items.add(item);
    notifyListeners();
    try {
      item.answer = await api.ask(question, audience);
    } on ApiException catch (e) {
      item.error = e.message;
    } catch (_) {
      item.error = 'Something went wrong. Please try again.';
    }
    item.loading = false;
    notifyListeners();
  }

  void addSurvey(Map<String, dynamic> data) {
    surveys.add(data);
  }
}

final AppState app = AppState();
