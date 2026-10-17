import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import 'error_messages.dart';
import 'mock_backend.dart';

class ApiException implements Exception {
  ApiException(this.code, {this.status, this.details, this.serverMessage});

  final String code;
  final int? status;
  final Map<String, dynamic>? details;
  final String? serverMessage;

  bool get isNetwork => code == 'NETWORK';
  String get message => friendlyMessage(code, status: status);

  @override
  String toString() => 'ApiException($code, $status, $serverMessage)';
}

class ApiClient {
  ApiClient()
      : dio = Dio(BaseOptions(
          connectTimeout: const Duration(seconds: 3),
          sendTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 15),
          contentType: Headers.jsonContentType,
          responseType: ResponseType.json,
        )) {
    dio.interceptors.add(mock);
  }

  final Dio dio;
  final mock = MockInterceptor();
  String baseUrl = '';
  String? token;
  void Function()? onUnauthorized;
  void Function(bool reachable)? onReachability;

  String url(String path) => '${baseUrl.trim().replaceAll(RegExp(r'/+$'), '')}$path';

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) =>
      request('GET', path, query: query);

  Future<dynamic> post(String path, Object? body, {bool auth = true}) =>
      request('POST', path, body: body, auth: auth);

  Future<dynamic> request(String method, String path,
      {Object? body, Map<String, dynamic>? query, bool auth = true}) async {
    for (var attempt = 0;; attempt++) {
      try {
        final res = await dio.request<dynamic>(
          url(path),
          data: body,
          queryParameters: query,
          options: Options(method: method, headers: {
            if (auth && token != null) 'Authorization': 'Bearer $token',
          }),
        );
        onReachability?.call(true);
        return decode(res.data);
      } on DioException catch (e) {
        final res = e.response;
        if (res == null) {
          if (e.type == DioExceptionType.cancel) rethrow;
          onReachability?.call(false);
          throw ApiException('NETWORK');
        }
        onReachability?.call(true);
        final status = res.statusCode ?? 0;
        if (status == 429 && attempt < 2) {
          final retry = int.tryParse(res.headers.value('retry-after') ?? '') ?? 2 * (attempt + 1);
          await Future<void>.delayed(Duration(seconds: retry.clamp(1, 10)));
          continue;
        }
        final data = decode(res.data);
        var code = switch (status) {
          401 => 'UNAUTHENTICATED',
          403 => 'FORBIDDEN',
          404 => 'NOT_FOUND',
          429 => 'RATE_LIMITED',
          400 || 422 => 'VALIDATION_ERROR',
          _ => 'SERVER_ERROR',
        };
        Map<String, dynamic>? details;
        String? serverMessage;
        if (data is Map && data['error'] is Map) {
          final err = data['error'] as Map;
          if (err['code'] is String) code = err['code'] as String;
          if (err['details'] is Map) details = Map<String, dynamic>.from(err['details'] as Map);
          serverMessage = err['message']?.toString();
        }
        if (status == 401 && auth) onUnauthorized?.call();
        throw ApiException(code, status: status, details: details, serverMessage: serverMessage);
      }
    }
  }

  static dynamic decode(dynamic d) {
    if (d is String && d.isNotEmpty) {
      try {
        return jsonDecode(d);
      } catch (_) {
        return d;
      }
    }
    return d;
  }
}
