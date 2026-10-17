import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/error_messages.dart';
import '../../core/nav.dart';
import '../../data/app_state.dart';
import '../../data/repository.dart';
import 'common.dart';

/// Shared load / error / offline-cache handling for screens.
mixin Loader<T extends StatefulWidget> on State<T> {
  Loaded? loaded;
  Object? error;
  bool loading = true;
  int _epoch = -1;

  AppState get app => context.read<AppState>();

  Future<Loaded> fetch();
  void onLoaded(Loaded l) {}

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) reload();
    });
  }

  Future<void> reload() async {
    if (mounted) setState(() => loading = true);
    try {
      final l = await fetch();
      if (!mounted) return;
      setState(() {
        loaded = l;
        error = null;
        loading = false;
      });
      onLoaded(l);
    } catch (e) {
      debugPrint('load failed: $e');
      if (!mounted) return;
      setState(() {
        error = e;
        loading = false;
      });
      if (loaded != null) showSnack(errorText(e), error: true);
    }
  }

  String errorText(Object e) {
    if (e is ApiException) return e.isNetwork ? offlineReadMessage : e.message;
    return serverErrorMessage;
  }

  Widget loadedBody(BuildContext context, Widget Function(dynamic data) builder) {
    final e = context.select<AppState, int>((s) => s.epoch);
    if (_epoch == -1) {
      _epoch = e;
    } else if (e != _epoch) {
      _epoch = e;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) reload();
      });
    }
    final l = loaded;
    if (l == null) {
      if (error != null && !loading) {
        return EmptyState(
          icon: Icons.error_outline,
          message: errorText(error!),
          actionLabel: 'Try again',
          onAction: reload,
        );
      }
      return const Center(child: CircularProgressIndicator(semanticsLabel: 'Loading'));
    }
    return Column(children: [
      if (l.fromCache) OfflineBanner(at: l.fetchedAt),
      Expanded(child: builder(l.data)),
    ]);
  }
}
