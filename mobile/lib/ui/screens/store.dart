import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config.dart';
import '../../core/formatters.dart';
import '../../core/theme.dart';
import '../../data/app_state.dart';
import '../../data/cart.dart';
import '../../data/repository.dart';
import '../widgets/sports.dart';
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
          const ExploreHeading('Store'),
          Expanded(
            child: RefreshIndicator(
              onRefresh: reload,
              child: GridView.count(
                padding: const EdgeInsets.all(12),
                crossAxisCount: MediaQuery.sizeOf(context).width >= 600 ? 3 : 2,
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                childAspectRatio: 0.72,
                children: [for (final p in items) ProductTile(product: p)],
              ),
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
    final name = '${product['name'] ?? ''}';
    const tiles = [Color(0xFFD84315), Color(0xFF1565C0), Color(0xFF2E7D32), Color(0xFF6A1B9A), Color(0xFF00838F)];
    final tile = tiles['${product['product_id']}'.hashCode.abs() % tiles.length];
    return Card(
      child: InkWell(
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute<void>(
            builder: (_) => ProductScreen(productId: product['product_id'] as String, product: product),
          ),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(
            child: Container(
              color: tile,
              alignment: Alignment.center,
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(categoryIcon(product['category'] as String?),
                    size: 44, color: Colors.white, semanticLabel: humanize(product['category'] as String?)),
                const SizedBox(height: 4),
                Text(name.isEmpty ? '' : name[0].toUpperCase(),
                    style: const TextStyle(color: Colors.white70, fontSize: 18, fontWeight: FontWeight.w800)),
              ]),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
              const SizedBox(height: 2),
              Text(price,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                      fontSize: 14, fontWeight: FontWeight.w800, color: AppColors.primary)),
              const SizedBox(height: 2),
              Text(stock <= 0 ? 'Sold out' : stock <= 5 ? '$stock left' : 'In stock',
                  style: t.textTheme.bodySmall?.copyWith(
                      color: stock <= 0 ? AppColors.live : AppColors.textSub,
                      fontWeight: stock <= 0 ? FontWeight.w700 : null)),
            ]),
          ),
        ]),
      ),
    );
  }
}
