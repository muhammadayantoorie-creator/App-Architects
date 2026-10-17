import 'package:flutter/foundation.dart';

class CartLine {
  CartLine({required this.product, required this.variant, required this.quantity});
  final Map<String, dynamic> product;
  final Map<String, dynamic> variant;
  int quantity;

  String get variantId => '${variant['variant_id']}';
  int get stock => (variant['stock'] as num?)?.toInt() ?? 0;
  int get unitMinor => (variant['price_minor'] as num?)?.toInt() ?? 0;
  int get totalMinor => unitMinor * quantity;
  String? get currency => variant['currency'] as String?;
  String get title => '${product['name'] ?? ''} (${variant['label'] ?? ''})';
}

/// In-memory cart. Checkout allows up to 10 distinct variants, quantity 1–10 each.
class Cart extends ChangeNotifier {
  final lines = <CartLine>[];

  int get count => lines.fold(0, (n, l) => n + l.quantity);
  int get totalMinor => lines.fold(0, (n, l) => n + l.totalMinor);
  bool get isEmpty => lines.isEmpty;

  /// Returns false when the cart already holds 10 different items.
  bool add(Map<String, dynamic> product, Map<String, dynamic> variant, int quantity) {
    final existing = lines.where((l) => l.variantId == '${variant['variant_id']}').firstOrNull;
    if (existing != null) {
      existing.quantity = (existing.quantity + quantity).clamp(1, maxQty(existing));
    } else {
      if (lines.length >= 10) return false;
      lines.add(CartLine(product: product, variant: variant, quantity: quantity));
    }
    notifyListeners();
    return true;
  }

  static int maxQty(CartLine l) => l.stock.clamp(1, 10);

  void setQuantity(CartLine line, int q) {
    line.quantity = q.clamp(1, maxQty(line));
    notifyListeners();
  }

  void remove(CartLine line) {
    lines.remove(line);
    notifyListeners();
  }

  void clear() {
    lines.clear();
    notifyListeners();
  }
}
