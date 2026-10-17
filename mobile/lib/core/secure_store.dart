import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// JWT lives only in the Android Keystore-backed secure storage.
class SecureStore {
  static const _key = 'jwt';
  final _storage = const FlutterSecureStorage();

  Future<String?> readToken() async {
    try {
      return await _storage.read(key: _key);
    } catch (_) {
      return null;
    }
  }

  Future<void> writeToken(String token) => _storage.write(key: _key, value: token);

  Future<void> clear() async {
    try {
      await _storage.delete(key: _key);
    } catch (_) {}
  }
}
