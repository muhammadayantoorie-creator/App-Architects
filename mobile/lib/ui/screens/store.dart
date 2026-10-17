import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config.dart';
import '../../core/formatters.dart';
import '../../data/app_state.dart';
import '../../data/cart.dart';
import '../../data/repository.dart';
import 'checkout.dart';
import '../widgets/common.dart';
import '../widgets/loader.dart';
import 'product.dart';

class StoreTab extends StatefulWidget {
  const StoreTab({super.key});

  @override
  State<StoreTab> createState() => _StoreTabState();
}

class _StoreTabState extends State<StoreTab> with Loader {
  @override
  Future<Loaded> fetch() => app.repo.products();

  @override
  Widget build(BuildContext context) => loadedBody(context, (d) {
        final items = asList(asMap(d)['items'])
          ..sort((a, b) => (a['product_id'] == demoProductId ? 0 : 1)
              .compareTo(b['product_id'] == demoProductId ? 0 : 1));
        if (items.isEmpty) {
          return RefreshIndicator(
            onRefresh: reload,
            child: const ScrollableEmpty(
              child: EmptyState(
                  icon: Icons.storefront_outlined,
                  message: 'The store has no products yet. Pull down to refresh.'),
            ),
          );
        }
        return Column(children: [
          Expanded(
            child: RefreshIndicator(
              onRefresh: reload,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                for (final p in items)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: ProductTile(product: p),
                  ),
              ]),
            ),
          ),
          const _CartBar(),
        ]);
      });
}

class _CartBar extends StatelessWidget {
  const _CartBar();

  @override
  Widget build(BuildContext context) {
    final cart = context.watch<Cart>();
    final canBuy = context.select<AppState, bool>((s) => s.canBuy);
    if (cart.isEmpty || !canBuy) return const SizedBox.shrink();
    final t = Theme.of(context);
    return Material(
      color: t.colorScheme.secondaryContainer,
      child: InkWell(
        onTap: () => Navigator.push(
            context, MaterialPageRoute<void>(builder: (_) => const CheckoutScreen())),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(children: [
            Icon(Icons.shopping_cart, color: t.colorScheme.onSecondaryContainer,
                semanticLabel: 'Cart'),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Cart · ${cart.count} ${cart.count == 1 ? 'item' : 'items'} · ${money(cart.totalMinor, cart.lines.first.currency)}',
                style: t.textTheme.titleSmall?.copyWith(color: t.colorScheme.onSecondaryContainer),
              ),
            ),
            Text('View cart',
                style: t.textTheme.labelLarge?.copyWith(color: t.colorScheme.onSecondaryContainer)),
            Icon(Icons.chevron_right, color: t.colorScheme.onSecondaryContainer,
                semanticLabel: 'View cart'),
          ]),
        ),
      ),
    );
  }
}

/// App-bar cart icon with item count.
class CartButton extends StatelessWidget {
  const CartButton({super.key});

  @override
  Widget build(BuildContext context) {
    final count = context.watch<Cart>().count;
    return IconButton(
      tooltip: count == 0 ? 'Cart (empty)' : 'Cart, $count items',
      onPressed: () => Navigator.push(
          context, MaterialPageRoute<void>(builder: (_) => const CheckoutScreen())),
      icon: Badge(
        isLabelVisible: count > 0,
        label: Text('$count'),
        child: Icon(Icons.shopping_cart_outlined,
            semanticLabel: count == 0 ? 'Cart (empty)' : 'Cart, $count items'),
      ),
    );
  }
}

IconData categoryIcon(String? category) => switch (category) {
      'apparel' => Icons.checkroom,
      'digital' || 'digital_items' || 'digital_item' => Icons.download_for_offline_outlined,
      _ => Icons.shopping_bag_outlined,
    };

int totalStock(Map<String, dynamic> p) =>
    asList(p['variants']).fold(0, (n, v) => n + ((v['stock'] as num?)?.toInt() ?? 0));

String stockLabel(int stock) => stock <= 0
    ? 'Sold out'
    : stock <= 5
        ? 'Only $stock left'
        : 'In stock';

class ProductTile extends StatelessWidget {
  const ProductTile({super.key, required this.product});
  final Map<String, dynamic> product;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final variants = asList(product['variants']);
    final prices = variants.map((v) => (v['price_minor'] as num?) ?? 0).toList()..sort();
    final currency = variants.isEmpty ? 'PKR' : variants.first['currency'] as String?;
    final stock = totalStock(product);
    final price = prices.isEmpty
        ? ''
        : prices.first == prices.last
            ? money(prices.first, currency)
            : 'From ${money(prices.first, currency)}';
    return Card(
      child: InkWell(
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute<void>(
            builder: (_) => ProductScreen(productId: product['product_id'] as String, product: product),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                  color: t.colorScheme.secondaryContainer, borderRadius: BorderRadius.circular(12)),
              child: Icon(categoryIcon(product['category'] as String?),
                  color: t.colorScheme.onSecondaryContainer, semanticLabel: 'Product'),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${product['name'] ?? ''}', style: t.textTheme.titleMedium),
                if (product['category'] != null)
                  Text(humanize(product['category'] as String?), style: t.textTheme.bodySmall),
                const SizedBox(height: 4),
                Text(price, style: t.textTheme.titleSmall),
              ]),
            ),
            Text(stockLabel(stock),
                style: t.textTheme.labelMedium?.copyWith(
                    color: stock <= 0 ? t.colorScheme.error : t.colorScheme.onSurfaceVariant)),
          ]),
        ),
      ),
    );
  }
}
