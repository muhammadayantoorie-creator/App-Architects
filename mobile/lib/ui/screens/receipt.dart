import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

import '../../core/formatters.dart';
import '../../core/nav.dart';
import '../../data/repository.dart';
import '../widgets/common.dart';
import '../widgets/network_chip.dart';

class ReceiptScreen extends StatefulWidget {
  const ReceiptScreen({super.key, required this.order, required this.names});

  final Map<String, dynamic> order;

  /// variant_id → "Product (Variant)"; order items only carry ids.
  final Map<String, String> names;

  @override
  State<ReceiptScreen> createState() => _ReceiptScreenState();
}

class _ReceiptScreenState extends State<ReceiptScreen> {
  bool _opening = false;

  Future<void> _openPdf() async {
    final b64 = asMap(widget.order['receipt'])['pdf_base64'] as String?;
    if (b64 == null || b64.isEmpty) {
      showSnack('The PDF receipt is not available for this order.', error: true);
      return;
    }
    setState(() => _opening = true);
    try {
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/receipt-${widget.order['order_id']}.pdf');
      await file.writeAsBytes(base64Decode(b64.replaceAll(RegExp(r'\s'), '')), flush: true);
      final r = await OpenFilex.open(file.path, type: 'application/pdf');
      if (r.type != ResultType.done) {
        showSnack('No app on this phone can open PDFs. Install a PDF viewer and try again.',
            error: true);
      }
    } catch (_) {
      showSnack("Couldn't open the receipt. Please try again.", error: true);
    } finally {
      if (mounted) setState(() => _opening = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final o = widget.order;
    final currency = o['currency'] as String?;
    final items = asList(o['items']);
    final status = '${o['status'] ?? 'paid'}';
    final paid = const ['paid', 'captured', 'completed', 'confirmed', 'succeeded'].contains(status);
    return PopScope(
      canPop: true,
      child: Scaffold(
        appBar: AppBar(title: const Text('Receipt'), actions: const [NetworkChip()]),
        body: SafeArea(
          child: ListView(padding: const EdgeInsets.all(16), children: [
            Center(
              child: Icon(paid ? Icons.check_circle : Icons.info_outline,
                  size: 56,
                  color: paid ? t.colorScheme.primary : t.colorScheme.onSurfaceVariant,
                  semanticLabel: paid ? 'Payment successful' : 'Order status'),
            ),
            const SizedBox(height: 8),
            Text(paid ? 'Payment successful' : humanize(status),
                textAlign: TextAlign.center, style: t.textTheme.headlineSmall),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Text('Order', style: t.textTheme.labelMedium),
                  SelectableText('${o['order_id'] ?? ''}', style: t.textTheme.bodyMedium),
                  const SizedBox(height: 8),
                  LabelValue('Status', paid ? 'Paid' : humanize(status)),
                  const Divider(),
                  for (final i in items)
                    LabelValue(
                      '${i['quantity'] ?? 1} × ${widget.names[i['variant_id']] ?? i['name'] ?? i['variant_id']}',
                      money((i['line_total_minor'] ??
                              ((i['unit_price_minor'] ?? i['price_minor'] ?? 0) as num) *
                                  ((i['quantity'] ?? 1) as num)) as num?,
                          currency),
                    ),
                  const Divider(),
                  LabelValue('Subtotal', money(o['subtotal_minor'] as num?, currency)),
                  LabelValue('Discount', '− ${money(o['discount_minor'] as num?, currency)}'),
                  LabelValue('Total', money(o['total_minor'] as num?, currency), bold: true),
                ]),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _opening ? null : _openPdf,
              icon: _opening
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, semanticsLabel: 'Opening'))
                  : const Icon(Icons.picture_as_pdf, semanticLabel: 'PDF receipt'),
              label: const Text('Open PDF receipt'),
            ),
            const SizedBox(height: 8),
            OutlinedButton(
              onPressed: () => Navigator.of(context).popUntil((r) => r.isFirst),
              child: const Text('Back to Store'),
            ),
          ]),
        ),
      ),
    );
  }
}
