import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

/// Printable/downloadable QR label. The product payload is deliberately the
/// stable product code consumed by the API QR resolver.
class ProductQrLabelDialog extends StatefulWidget {
  const ProductQrLabelDialog({
    super.key,
    required this.productCode,
    required this.productName,
    this.lotId,
    this.lotNumber,
  });

  final String productCode;
  final String productName;
  final int? lotId;
  final String? lotNumber;

  String get _payload => lotId == null
      ? productCode
      : 'MANUFLOW|$productCode|${lotNumber ?? lotId}';

  String get _fileName => lotId == null
      ? 'qr-product-$productCode'
      : 'qr-lot-$productCode-${lotNumber ?? lotId}';

  @override
  State<ProductQrLabelDialog> createState() => _ProductQrLabelDialogState();
}

class _ProductQrLabelDialogState extends State<ProductQrLabelDialog> {
  bool _saving = false;

  Future<void> _download() async {
    setState(() => _saving = true);
    try {
      final painter = QrPainter(
        data: widget._payload,
        version: QrVersions.auto,
        gapless: false,
      );
      final data = await painter.toImageData(
        768,
        format: ui.ImageByteFormat.png,
      );
      if (data == null) throw StateError('Unable to generate QR image.');
      await FileSaver.instance.saveFile(
        name: widget._fileName,
        bytes: Uint8List.view(data.buffer),
        fileExtension: 'png',
        mimeType: MimeType.png,
      );
      if (mounted) Navigator.pop(context);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to download the QR label.')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Product QR Label'),
    content: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        QrImageView(data: widget._payload, size: 240),
        const SizedBox(height: 12),
        Text(
          widget.productCode,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        Text(widget.productName, textAlign: TextAlign.center),
        if (widget.lotNumber != null) Text('Lot ${widget.lotNumber}'),
      ],
    ),
    actions: [
      TextButton(
        onPressed: _saving ? null : () => Navigator.pop(context),
        child: const Text('Close'),
      ),
      FilledButton.icon(
        onPressed: _saving ? null : _download,
        icon: const Icon(Icons.download),
        label: Text(_saving ? 'Preparing…' : 'Download PNG'),
      ),
    ],
  );
}

/// Full-screen variant used by product actions on mobile and web.
/// Keeping it separate from [ProductQrLabelDialog] avoids relying on a dialog
/// layout when it is rendered as a normal route.
class ProductQrLabelPage extends StatefulWidget {
  const ProductQrLabelPage({
    super.key,
    required this.productCode,
    required this.productName,
  });

  final String productCode;
  final String productName;

  @override
  State<ProductQrLabelPage> createState() => _ProductQrLabelPageState();
}

class _ProductQrLabelPageState extends State<ProductQrLabelPage> {
  bool _saving = false;

  Future<void> _download() async {
    setState(() => _saving = true);
    try {
      final painter = QrPainter(
        data: widget.productCode,
        version: QrVersions.auto,
        gapless: false,
      );
      final image = await painter.toImageData(
        768,
        format: ui.ImageByteFormat.png,
      );
      if (image == null) throw StateError('Unable to generate QR image.');
      await FileSaver.instance.saveFile(
        name: 'qr-product-${widget.productCode}',
        bytes: Uint8List.view(image.buffer),
        fileExtension: 'png',
        mimeType: MimeType.png,
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to download the QR label.')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Product QR Label')),
    body: Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              widget.productCode,
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            Text(widget.productName, textAlign: TextAlign.center),
            const SizedBox(height: 20),
            Container(
              color: Colors.white,
              padding: const EdgeInsets.all(12),
              child: QrImageView(data: widget.productCode, size: 280),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: _saving ? null : _download,
              icon: const Icon(Icons.download),
              label: Text(_saving ? 'Preparing…' : 'Download PNG'),
            ),
          ],
        ),
      ),
    ),
  );
}
