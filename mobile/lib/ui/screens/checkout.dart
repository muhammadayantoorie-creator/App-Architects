import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/config.dart';
import '../../core/error_messages.dart';
import '../../core/formatters.dart';
import '../../data/app_state.dart';
import '../../data/cart.dart';
import '../widgets/common.dart';
import '../widgets/network_chip.dart';
import 'receipt.dart';

/// Cart + checkout. With [buyNow] it checks out just that line; otherwise the shared cart.
class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key, this.buyNow});
  final CartLine? buyNow;

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

  bool get _isCart => widget.buyNow == null;

  List<CartLine> _lines(Cart cart) => _isCart ? cart.lines : [widget.buyNow!];

  Future<void> _pay(List<CartLine> lines) async {
    final currency = lines.first.currency;
    final subtotal = lines.fold<int>(0, (n, l) => n + l.totalMinor);
    final code = _discount.text.trim();
    final ok = await confirmDialog(context,
        title: 'Pay ${money(subtotal, currency)}?',
        message: '${lines.map((l) => '${l.quantity} × ${l.title}').join('\n')}'
            '${code.isEmpty ? '' : '\nDiscount code $code will be applied if valid.'}',
        confirmLabel: 'Pay');
    if (!ok || !mounted) return;
    final s = context.read<AppState>();
    final cart = context.read<Cart>();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final res = await s.api.post('/api/v1/checkout', {
        'order_id': _orderId,
        'customer_id': s.userId,
        'items': [
          for (final l in lines) {'variant_id': l.variantId, 'quantity': l.quantity},
        ],
        'discount_code': code.isEmpty ? null : code,
        'payment': {'token': _token},
      });
      if (!mounted) return;
      final names = {for (final l in lines) l.variantId: l.title};
      if (_isCart) cart.clear();
      await Navigator.pushReplacement(
        context,
        MaterialPageRoute<void>(
          builder: (_) =>
              ReceiptScreen(order: Map<String, dynamic>.from(res as Map), names: names),
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
    final cart = context.watch<Cart>();
    final lines = _lines(cart);
    final currency = lines.isEmpty ? 'PKR' : lines.first.currency;
    final subtotal = lines.fold<int>(0, (n, l) => n + l.totalMinor);
    return Scaffold(
      appBar: AppBar(title: Text(_isCart ? 'Cart' : 'Checkout'), actions: const [NetworkChip()]),
      body: SafeArea(
        child: lines.isEmpty
            ? EmptyState(
                icon: Icons.shopping_cart_outlined,
                message: 'Your cart is empty. Add items from the Store.',
                actionLabel: 'Back to Store',
                onAction: () => Navigator.pop(context),
              )
            : ListView(padding: const EdgeInsets.all(16), children: [
                for (final l in lines)
                  Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(12, 8, 4, 8),
                      child: Row(children: [
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text('${l.product['name']}', style: t.textTheme.titleSmall),
                            Text('${l.variant['label']} · ${money(l.unitMinor, l.currency)} each',
                                style: t.textTheme.bodySmall),
                            const SizedBox(height: 4),
                            Text(money(l.totalMinor, l.currency),
                                style: t.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold)),
                          ]),
                        ),
                        if (_isCart) ...[
                          IconButton(
                            tooltip: 'Decrease quantity',
                            onPressed: l.quantity > 1 && !_busy
                                ? () => cart.setQuantity(l, l.quantity - 1)
                                : null,
                            icon: const Icon(Icons.remove, semanticLabel: 'Decrease quantity'),
                          ),
                          Text('${l.quantity}',
                              style: t.textTheme.titleMedium, semanticsLabel: 'Quantity ${l.quantity}'),
                          IconButton(
                            tooltip: 'Increase quantity',
                            onPressed: l.quantity < Cart.maxQty(l) && !_busy
                                ? () => cart.setQuantity(l, l.quantity + 1)
                                : null,
                            icon: const Icon(Icons.add, semanticLabel: 'Increase quantity'),
                          ),
                          IconButton(
                            tooltip: 'Remove from cart',
                            onPressed: _busy ? null : () => cart.remove(l),
                            icon: const Icon(Icons.delete_outline, semanticLabel: 'Remove from cart'),
                          ),
                        ] else
                          Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: Text('Qty ${l.quantity}', style: t.textTheme.titleSmall),
                          ),
                      ]),
                    ),
                  ),
                const SizedBox(height: 8),
                TextField(
                  controller: _discount,
                  textCapitalization: TextCapitalization.characters,
                  onChanged: (_) => setState(() {}),
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
                LabelValue('Subtotal', money(subtotal, currency)),
                LabelValue('Discount',
                    _discount.text.trim().isEmpty ? money(0, currency) : 'Applied at payment'),
                const Divider(),
                LabelValue('Total', money(subtotal, currency), bold: true),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Semantics(
                    liveRegion: true,
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                          color: t.colorScheme.errorContainer,
                          borderRadius: BorderRadius.circular(12)),
                      child: Row(children: [
                        Icon(Icons.error_outline,
                            color: t.colorScheme.onErrorContainer, semanticLabel: 'Error'),
                        const SizedBox(width: 8),
                        Expanded(
                            child: Text(_error!,
                                style: TextStyle(color: t.colorScheme.onErrorContainer))),
                      ]),
                    ),
                  ),
                ],
              ]),
      ),
      bottomNavigationBar: lines.isEmpty
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                child: FilledButton.icon(
                  onPressed: _busy ? null : () => _pay(List.of(lines)),
                  icon: _busy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, semanticsLabel: 'Paying'))
                      : const Icon(Icons.lock_outline, semanticLabel: 'Pay'),
                  label: Text(_busy ? 'Processing payment…' : 'Pay ${money(subtotal, currency)}'),
                ),
              ),
            ),
    );
  }
}
