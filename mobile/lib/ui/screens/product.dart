import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/formatters.dart';
import '../../core/nav.dart';
import '../../data/app_state.dart';
import '../../data/cart.dart';
import '../../data/repository.dart';
import '../widgets/loader.dart';
import '../widgets/network_chip.dart';
import 'checkout.dart';
import 'store.dart';

class ProductScreen extends StatefulWidget {
  const ProductScreen({super.key, required this.productId, this.product});
  final String productId;
  final Map<String, dynamic>? product;

  @override
  State<ProductScreen> createState() => _ProductScreenState();
}

class _ProductScreenState extends State<ProductScreen> with Loader {
  String? _variantId;
  int _qty = 1;

  @override
  Future<Loaded> fetch() async {
    final l = await app.repo.products();
    final p = asList(asMap(l.data)['items']).firstWhere(
      (i) => i['product_id'] == widget.productId,
      orElse: () => widget.product ?? {},
    );
    return Loaded(p, fromCache: l.fromCache, fetchedAt: l.fetchedAt);
  }

  @override
  void onLoaded(Loaded l) {
    final variants = asList(asMap(l.data)['variants']);
    final current = variants.where((v) => v['variant_id'] == _variantId).firstOrNull;
    if (current == null || ((current['stock'] as num?) ?? 0) <= 0) {
      final first = variants.where((v) => ((v['stock'] as num?) ?? 0) > 0).firstOrNull;
      setState(() => _variantId = first?['variant_id'] as String?);
    }
  }

  void _addToCart(Map<String, dynamic> p, Map<String, dynamic> v) {
    final ok = context.read<Cart>().add(p, v, _qty);
    if (!ok) {
      showSnack('Your cart already has 10 different items. Check out first.', error: true);
      return;
    }
    showSnack(
      'Added $_qty × ${p['name']} (${v['label']}) to your cart.',
      action: SnackBarAction(
        label: 'View cart',
        onPressed: () => navKey.currentState
            ?.push(MaterialPageRoute<void>(builder: (_) => const CheckoutScreen())),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canBuy = context.select<AppState, bool>((s) => s.canBuy);
    final p = asMap(loaded?.data ?? widget.product);
    final variants = asList(p['variants']);
    final v = variants.where((x) => x['variant_id'] == _variantId).firstOrNull;
    final stock = (v?['stock'] as num?)?.toInt() ?? 0;
    final total = ((v?['price_minor'] as num?) ?? 0) * _qty;
    return Scaffold(
      appBar: AppBar(
        title: Text('${p['name'] ?? 'Product'}', overflow: TextOverflow.ellipsis),
        actions: [if (canBuy) const CartButton(), const NetworkChip()],
      ),
      body: SafeArea(child: loadedBody(context, (_) => _details(context, p, variants, stock))),
      bottomNavigationBar: loaded == null || p.isEmpty
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                child: canBuy
                    ? Column(mainAxisSize: MainAxisSize.min, children: [
                        if (v != null && stock > 0)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: Text('Total: ${money(total, v['currency'] as String?)}',
                                style: Theme.of(context).textTheme.titleMedium),
                          ),
                        Row(children: [
                          Expanded(
                            child: OutlinedButton(
                              onPressed: v == null || stock <= 0 ? null : () => _addToCart(p, v),
                              child: const Text('Add to cart'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: FilledButton(
                              onPressed: v == null || stock <= 0
                                  ? null
                                  : () => Navigator.push(
                                        context,
                                        MaterialPageRoute<void>(
                                          builder: (_) => CheckoutScreen(
                                            buyNow: CartLine(product: p, variant: v, quantity: _qty),
                                          ),
                                        ),
                                      ),
                              child: Text(v == null || stock <= 0 ? 'Sold out' : 'Buy now'),
                            ),
                          ),
                        ]),
                      ])
                    : const Text('Viewer accounts can browse the store but not buy.',
                        textAlign: TextAlign.center),
              ),
            ),
    );
  }

  Widget _details(BuildContext context, Map<String, dynamic> p,
      List<Map<String, dynamic>> variants, int stock) {
    final t = Theme.of(context);
    if (p.isEmpty) {
      return const Center(child: Text("We couldn't find that item. It may have been removed."));
    }
    final v = variants.where((x) => x['variant_id'] == _variantId).firstOrNull;
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text('${p['name'] ?? ''}', style: t.textTheme.headlineSmall),
      if (p['category'] != null)
        Text(humanize(p['category'] as String?), style: t.textTheme.bodyMedium),
      const SizedBox(height: 8),
      if (v != null)
        Text(money(v['price_minor'] as num?, v['currency'] as String?),
            style: t.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
      if (p['description'] != null) ...[
        const SizedBox(height: 12),
        Text('${p['description']}', style: t.textTheme.bodyLarge),
      ],
      const SizedBox(height: 24),
      Text('Choose an option', style: t.textTheme.titleMedium),
      const SizedBox(height: 8),
      Wrap(spacing: 8, runSpacing: 8, children: [
        for (final x in variants)
          Builder(builder: (_) {
            final s = (x['stock'] as num?)?.toInt() ?? 0;
            return ChoiceChip(
              label: Text(s <= 0 ? '${x['label']} · Sold out' : '${x['label']}'),
              selected: x['variant_id'] == _variantId,
              onSelected: s <= 0
                  ? null
                  : (_) => setState(() {
                        _variantId = x['variant_id'] as String?;
                        _qty = 1;
                      }),
            );
          }),
      ]),
      const SizedBox(height: 8),
      Text(stockLabel(stock),
          style: t.textTheme.bodyMedium
              ?.copyWith(color: stock <= 0 ? t.colorScheme.error : t.colorScheme.onSurfaceVariant)),
      const SizedBox(height: 24),
      Text('Quantity', style: t.textTheme.titleMedium),
      const SizedBox(height: 8),
      Row(children: [
        IconButton.outlined(
          tooltip: 'Decrease quantity',
          onPressed: _qty > 1 ? () => setState(() => _qty--) : null,
          icon: const Icon(Icons.remove, semanticLabel: 'Decrease quantity'),
        ),
        SizedBox(
          width: 48,
          child: Text('$_qty',
              textAlign: TextAlign.center,
              style: t.textTheme.titleLarge,
              semanticsLabel: 'Quantity $_qty'),
        ),
        IconButton.outlined(
          tooltip: 'Increase quantity',
          onPressed: _qty < stock && _qty < 10 ? () => setState(() => _qty++) : null,
          icon: const Icon(Icons.add, semanticLabel: 'Increase quantity'),
        ),
      ]),
    ]);
  }
}
