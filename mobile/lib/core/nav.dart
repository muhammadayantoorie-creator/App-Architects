import 'package:flutter/material.dart';

final navKey = GlobalKey<NavigatorState>();
final messengerKey = GlobalKey<ScaffoldMessengerState>();

void showSnack(String message, {bool error = false, SnackBarAction? action}) {
  final m = messengerKey.currentState;
  if (m == null) return;
  m.hideCurrentSnackBar();
  m.showSnackBar(SnackBar(
    content: Row(children: [
      Icon(error ? Icons.error_outline : Icons.check_circle_outline,
          color: Colors.white, semanticLabel: error ? 'Error' : 'Success'),
      const SizedBox(width: 12),
      Expanded(child: Text(message)),
    ]),
    action: action,
    duration: Duration(seconds: error ? 6 : 4),
  ));
}
