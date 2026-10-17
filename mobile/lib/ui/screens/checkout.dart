import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/config.dart';
import '../../core/error_messages.dart';
import '../../core/formatters.dart';
import '../../data/app_state.dart';
import '../widgets/common.dart';
import '../widgets/network_chip.dart';
import 'receipt.dart';

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({
    super.key,
    required this.product,
    required this.variant,
    required this.quantity,
  });

  final Map<String, dynamic> product;
  final Map<String, dynamic> variant;
  final int quantity;

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  // One order id per checkout attempt; reused when retrying after a network failure.
  String _orderId = newId();
  final _discount = TextEditingController();
  String _token = paymentOptions.first.$1;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _discount.dispose();
    super.dispose();
  }

  String? get _currency => widget.variant['currency'] as String?;
  num get _subtotal => ((widget.variant['price_minor'] as num?) ?? 0) * widget.quantity;

  Future<void> _pay() async {
    final ok = await confirmDialog(context,
        title: 'Pay ${money(_subtotal, _currency)}?',
        message:
            '${widget.quantity} × ${widget.product['name']} (${widget.variant['label']}).'
            '${_discount.text.trim().isEmpty ? '' : ' Discount code ${_discount.text.trim()} will be applied if valid.'}',
        confirmLabel: 'Pay');
    if (!ok || !mounted) return;
    final s = context.read<AppState>();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final res = await s.api.post('/api/v1/checkout', {
        'order_id': _orderId,
        'customer_id': s.userId,
        'items': [
          {'variant_id': widget.variant['variant_id'], 'quantity': widget.quantity},
        ],
        'discount_code': _discount.text.trim().isEmpty ? null : _discount.text.trim(),
        'payment': {'token': _token},
      });
      if (!mounted) return;
      await Navigator.pushReplacement(
        context,
        MaterialPageRoute<void>(
          builder: (_) => ReceiptScreen(
            order: Map<String, dynamic>.from(res as Map),
            productName: '${widget.product['name']}',
            variantLabel: '${widget.variant['label']}',
          ),
        ),
      );
    } on ApiException catch (e) {
      setState(() {
        if (e.isNetwork) {
          _error = offlineNoQueueMessage;
        } else {
          _error = e.status == 402 && e.code != 'PAYMENT_CAPTURE_FAILED'
              ? friendlyMessage('PAYMENT_DECLINED')
              : e.message;
          // The server answered: a new attempt gets a fresh order id.
          if ((e.status ?? 500) < 500) _orderId = newId();
        }
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Checkout'), actions: const [NetworkChip()]),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.checkroom, semanticLabel: 'Item'),
              title: Text('${widget.product['name']}'),
              subtitle: Text('${widget.variant['label']} · Qty ${widget.quantity}'),
              trailing: Text(money(_subtotal, _currency), style: t.textTheme.titleSmall),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _discount,
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(
              labelText: 'Discount code (optional)',
              prefixIcon: Icon(Icons.local_offer_outlined),
            ),
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            initialValue: _token,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Payment method (test gateway)',
              prefixIcon: Icon(Icons.credit_card),
            ),
            items: [
              for (final (token, label) in paymentOptions)
                DropdownMenuItem(value: token, child: Text(label)),
            ],
            onChanged: (v) => setState(() => _token = v ?? _token),
          ),
          const SizedBox(height: 16),
          LabelValue('Subtotal', money(_subtotal, _currency)),
          LabelValue('Discount',
              _discount.text.trim().isEmpty ? money(0, _currency) : 'Applied at payment'),
          const Divider(),
          LabelValue('Total', money(_subtotal, _currency), bold: true),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Semantics(
              liveRegion: true,
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                    color: t.colorScheme.errorContainer, borderRadius: BorderRadius.circular(12)),
                child: Row(children: [
                  Icon(Icons.error_outline,
                      color: t.colorScheme.onErrorContainer, semanticLabel: 'Error'),
                  const SizedBox(width: 8),
                  Expanded(
                      child: Text(_error!, style: TextStyle(color: t.colorScheme.onErrorContainer))),
                ]),
              ),
            ),
          ],
        ]),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: FilledButton.icon(
            onPressed: _busy ? null : _pay,
            icon: _busy
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, semanticsLabel: 'Paying'))
                : const Icon(Icons.lock_outline, semanticLabel: 'Pay'),
            label: Text(_busy ? 'Processing payment…' : 'Pay ${money(_subtotal, _currency)}'),
          ),
        ),
      ),
    );
  }
}
