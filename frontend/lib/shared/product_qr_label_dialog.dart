import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import 'modal_widgets.dart';

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
      final data = await opaqueQrPng(widget._payload, 768);
      await FileSaver.instance.saveFile(
        name: widget._fileName,
        bytes: data,
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
        QrPayloadImage(data: widget._payload, size: 240),
        const SizedBox(height: 12),
        CopyableCodeText(
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
  State<ProductQrLabelPage> createState() => _ProductQrLabelPageState();
}

class _ProductQrLabelPageState extends State<ProductQrLabelPage> {
  bool _saving = false;

  Future<void> _download() async {
    setState(() => _saving = true);
    try {
      final image = await opaqueQrPng(widget._payload, 768);
      await FileSaver.instance.saveFile(
        name: widget._fileName,
        bytes: image,
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
            CopyableCodeText(
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
              child: QrPayloadImage(data: widget._payload, size: 280),
            ),
            if (widget.lotNumber != null) ...[
              const SizedBox(height: 6),
              Text('Lot ${widget.lotNumber}'),
            ],
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

/// Rasterized QR preview used everywhere in the Flutter UI.
///
/// Rendering to PNG avoids a silent Canvas rendering failure that can occur
/// with direct [QrImageView] previews on some web/desktop renderers.
class QrPayloadImage extends StatefulWidget {
  const QrPayloadImage({super.key, required this.data, required this.size});

  final String data;
  final double size;

  @override
  State<QrPayloadImage> createState() => _QrPayloadImageState();
}

class _QrPayloadImageState extends State<QrPayloadImage> {
  late Future<Uint8List> _image;

  @override
  void initState() {
    super.initState();
    _image = _render();
  }

  @override
  void didUpdateWidget(covariant QrPayloadImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.data != widget.data || oldWidget.size != widget.size) {
      _image = _render();
    }
  }

  Future<Uint8List> _render() async {
    return opaqueQrPng(widget.data, widget.size * 3);
  }

  @override
  Widget build(BuildContext context) => SizedBox(
    width: widget.size,
    height: widget.size,
    child: FutureBuilder<Uint8List>(
      future: _image,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return const DecoratedBox(
            decoration: BoxDecoration(color: Colors.white),
            child: Center(
              child: Text(
                'QR preview unavailable',
                textAlign: TextAlign.center,
              ),
            ),
          );
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        return ColoredBox(
          color: Colors.white,
          child: Image.memory(
            snapshot.data!,
            width: widget.size,
            height: widget.size,
            filterQuality: FilterQuality.none,
          ),
        );
      },
    ),
  );
}

/// Renders a portable QR PNG with an opaque white background. A transparent
/// background is rendered dark by some viewers and printers, making a QR
/// unreadable even though its on-screen preview appears correct.
Future<Uint8List> opaqueQrPng(String payload, double size) async {
  final recorder = ui.PictureRecorder();
  final canvas = ui.Canvas(recorder);
  final renderSize = ui.Size.square(size);
  canvas.drawColor(Colors.white, ui.BlendMode.src);
  final painter = QrPainter(
    data: payload,
    version: QrVersions.auto,
    gapless: false,
    eyeStyle: const QrEyeStyle(color: Colors.black),
    dataModuleStyle: const QrDataModuleStyle(color: Colors.black),
  );
  painter.paint(canvas, renderSize);
  final picture = recorder.endRecording();
  final image = await picture.toImage(size.round(), size.round());
  final data = await image.toByteData(format: ui.ImageByteFormat.png);
  image.dispose();
  if (data == null) throw StateError('Unable to render QR image.');
  return data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
}
