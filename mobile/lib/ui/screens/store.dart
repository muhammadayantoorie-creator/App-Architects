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
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 0.66,
                children: [
                  for (var i = 0; i < items.length; i++) ProductTile(product: items[i], featured: i == 0),
                ],
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
    const ink = AppColors.onPrimary;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
      child: Material(
        color: AppColors.primary,
        shape: const StadiumBorder(),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => Navigator.push(
              context, MaterialPageRoute<void>(builder: (_) => const CheckoutScreen())),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(8, 8, 16, 8),
            child: Row(children: [
              const CircleAvatar(
                radius: 20,
                backgroundColor: ink,
                child: Icon(Icons.shopping_cart, color: AppColors.primary, semanticLabel: 'Cart'),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  '${cart.count} ${cart.count == 1 ? 'ITEM' : 'ITEMS'} · ${money(cart.totalMinor, cart.lines.first.currency)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                      fontFamily: condensedFont, color: ink, fontSize: 18, fontWeight: FontWeight.w800),
                ),
              ),
              const Text('VIEW CART',
                  style: TextStyle(
                      fontFamily: condensedFont, color: ink, fontSize: 16, fontWeight: FontWeight.w900)),
              const Icon(Icons.chevron_right, color: ink, semanticLabel: 'View cart'),
            ]),
          ),
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

/// Bundled product artwork, picked from the product's name/category.
String productArt(Map<String, dynamic> p) {
  final s = '${p['name'] ?? ''} ${p['category'] ?? ''}'.toLowerCase();
  if (s.contains('scarf')) return 'assets/products/scarf.png';
  if (s.contains('cap') || s.contains('hat')) return 'assets/products/cap.png';
  if (s.contains('jersey') || s.contains('shirt') || s.contains('kit') || s.contains('apparel')) {
    return 'assets/products/jersey.png';
  }
  if (s.contains('digital') || s.contains('ticket') || s.contains('pass')) {
    return 'assets/products/digital.png';
  }
  return 'assets/products/bag.png';
}

int totalStock(Map<String, dynamic> p) =>
    asList(p['variants']).fold(0, (n, v) => n + ((v['stock'] as num?)?.toInt() ?? 0));

String stockLabel(int stock) => stock <= 0
    ? 'Sold out'
    : stock <= 5
        ? 'Only $stock left'
        : 'In stock';

class ProductTile extends StatelessWidget {
  const ProductTile({super.key, required this.product, this.featured = false});
  final Map<String, dynamic> product;
  final bool featured;

  @override
  Widget build(BuildContext context) {
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
    final category = humanize(product['category'] as String?);
    const ink = Color(0xFF0B0B0B);
    const condensed = TextStyle(fontFamily: condensedFont, color: ink, fontWeight: FontWeight.w800);
    final stockText = stock <= 0 ? 'SOLD OUT' : stock <= 5 ? '$stock LEFT' : 'IN STOCK';
    return Semantics(
      button: true,
      label: '$name, $category, $price, ${stockLabel(stock)}',
      child: ExcludeSemantics(
        child: Material(
          color: const Color(0xFFF2F2F2),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
          clipBehavior: Clip.antiAlias,
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
                  decoration: BoxDecoration(
                    color: featured ? AppColors.primary : const Color(0xFFCFCFCF),
                    borderRadius: BorderRadius.circular(28),
                  ),
                  child: Stack(children: [
                    Positioned.fill(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(14, 34, 14, 8),
                        child: Image.asset(productArt(product), fit: BoxFit.contain),
                      ),
                    ),
                    Positioned(
                      top: 10,
                      left: 10,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.85),
                            borderRadius: BorderRadius.circular(20)),
                        child: Text(category.toUpperCase(),
                            style: condensed.copyWith(fontSize: 12, letterSpacing: 0.5)),
                      ),
                    ),
                  ]),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(name.toUpperCase(),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: condensed.copyWith(fontSize: 18, height: 1.05)),
                  const SizedBox(height: 2),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(price,
                        style: condensed.copyWith(fontSize: 24, fontWeight: FontWeight.w900, height: 1.1)),
                  ),
                  const SizedBox(height: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: stock <= 0 ? AppColors.live : ink,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(stockText,
                        style: condensed.copyWith(
                            fontSize: 12,
                            letterSpacing: 0.5,
                            color: stock <= 0 || stock > 5 ? Colors.white : AppColors.primary)),
                  ),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
