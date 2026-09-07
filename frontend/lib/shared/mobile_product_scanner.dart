import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../core/api_client.dart';

bool get supportsMobileProductScanner =>
    !kIsWeb &&
    (defaultTargetPlatform == TargetPlatform.android ||
        defaultTargetPlatform == TargetPlatform.iOS);

class ScannedProductIdentity {
  const ScannedProductIdentity({
    required this.productCode,
    required this.productName,
    required this.description,
    this.lotId,
    this.lotNumber,
    this.unit,
    this.availableQuantity,
  });

  factory ScannedProductIdentity.fromJson(Map<String, dynamic> json) =>
      ScannedProductIdentity(
        productCode: json['product_code'].toString(),
        productName: json['product_name'].toString(),
        description: json['description'].toString(),
        lotId: json['lot_id'] as int?,
        lotNumber: json['lot_number']?.toString(),
        unit: json['unit']?.toString(),
        availableQuantity: num.tryParse(json['available_quantity'].toString()),
      );

  final String productCode;
  final String productName;
  final String description;
  final int? lotId;
  final String? lotNumber;
  final String? unit;
  final num? availableQuantity;

  String get key => '$productCode:${lotId ?? lotNumber ?? ''}';
}

class MobileProductScannerDialog extends StatefulWidget {
  const MobileProductScannerDialog({super.key, required this.api});
  final ApiClient api;

  @override
  State<MobileProductScannerDialog> createState() =>
      _MobileProductScannerDialogState();
}

class _MobileProductScannerDialogState
    extends State<MobileProductScannerDialog> {
  final _controller = MobileScannerController();
  final _items = <ScannedProductIdentity>[];
  bool _resolving = false;
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _detect(BarcodeCapture capture) async {
    final payload = capture.barcodes.firstOrNull?.rawValue?.trim();
    if (_resolving || payload == null || payload.isEmpty) return;
    setState(() {
      _resolving = true;
      _error = null;
    });
    await _controller.stop();
    try {
      final response = await widget.api.getJson(
        '/master-data/products/qr-resolve?payload=${Uri.encodeQueryComponent(payload)}',
      );
      final item = ScannedProductIdentity.fromJson(
        response as Map<String, dynamic>,
      );
      if (mounted) {
        setState(() {
          if (!_items.any((existing) => existing.key == item.key)) {
            _items.add(item);
          }
        });
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) {
        setState(() => _resolving = false);
        await _controller.start();
      }
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Scan Product QR'),
    content: SizedBox(
      width: 560,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AspectRatio(
            aspectRatio: 1.2,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: MobileScanner(controller: _controller, onDetect: _detect),
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            ),
          const SizedBox(height: 10),
          Text('${_items.length} product / lot scanned'),
          SizedBox(
            height: 120,
            child: ListView.builder(
              itemCount: _items.length,
              itemBuilder: (_, index) {
                final item = _items[index];
                return ListTile(
                  dense: true,
                  title: Text('${item.productCode} — ${item.productName}'),
                  subtitle: Text(
                    item.lotNumber == null
                        ? 'Product QR'
                        : 'Lot ${item.lotNumber}',
                  ),
                  trailing: IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => setState(() => _items.removeAt(index)),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: _items.isEmpty ? null : () => Navigator.pop(context, _items),
        child: const Text('Use Scanned Items'),
      ),
    ],
  );
}

Future<List<ScannedProductIdentity>?> scanProducts(
  BuildContext context,
  ApiClient api,
) {
  if (!supportsMobileProductScanner) return Future.value(null);
  return showDialog<List<ScannedProductIdentity>>(
    context: context,
    barrierDismissible: false,
    builder: (_) => MobileProductScannerDialog(api: api),
  );
}
