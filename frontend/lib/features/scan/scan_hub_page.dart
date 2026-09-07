import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart';
import '../../shared/mobile_product_scanner.dart';
import '../auth/auth_controller.dart';
import '../delivery/delivery_page.dart';
import '../production/production_models.dart';
import '../production/wip_execution_form_dialog.dart';
import '../quality/quality_inspection_form_dialog.dart';
import '../quality/quality_models.dart';
import '../receiving/receiving_form_dialog.dart';

/// Mobile-only entry point for QR-assisted operational transactions.
///
/// It does not post any inventory movement itself. Each action opens the
/// existing reviewed form, so all normal validations and approvals remain in
/// force.
class ScanHubPage extends StatefulWidget {
  const ScanHubPage({super.key, required this.auth});

  final AuthController auth;

  @override
  State<ScanHubPage> createState() => _ScanHubPageState();
}

class _ScanHubPageState extends State<ScanHubPage> {
  final List<ScannedProductIdentity> _scans = [];
  bool _opening = false;
  String? _error;

  Future<void> _scan() async {
    final scans = await scanProducts(context, widget.auth.api);
    if (scans == null || scans.isEmpty || !mounted) return;
    setState(() {
      _error = null;
      for (final scan in scans) {
        if (!_scans.any((existing) => existing.key == scan.key)) {
          _scans.add(scan);
        }
      }
    });
  }

  Future<void> _openReceiving() async {
    await _open(
      () => showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => ReceivingFormDialog(
          auth: widget.auth,
          scannedProductCodes: _scans.map((item) => item.productCode).toList(),
        ),
      ),
    );
  }

  Future<void> _openDelivery() async {
    final invalid = _scans.where((scan) => scan.lotId == null).isNotEmpty;
    if (invalid) {
      setState(
        () => _error = 'Delivery requires a QR label for a Finished Good lot.',
      );
      return;
    }
    await _open(
      () => showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) =>
            DeliveryFormDialog(auth: widget.auth, initialScans: _scans),
      ),
    );
  }

  Future<void> _openWip() async {
    final job = await _singleWipJob();
    if (job == null || !mounted) return;
    await _open(
      () => showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => WipExecutionFormDialog(api: widget.auth.api, job: job),
      ),
    );
  }

  Future<void> _openQuality() async {
    final job = await _singleQualityJob();
    if (job == null || !mounted) return;
    await _open(
      () => showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) =>
            QualityInspectionFormDialog(api: widget.auth.api, job: job),
      ),
    );
  }

  Future<void> _open(Future<bool?> Function() openDialog) async {
    setState(() {
      _opening = true;
      _error = null;
    });
    try {
      await openDialog();
    } finally {
      if (mounted) setState(() => _opening = false);
    }
  }

  ScannedProductIdentity? get _singleScan {
    if (_scans.length == 1) return _scans.single;
    setState(() => _error = 'Scan exactly one product / lot for this action.');
    return null;
  }

  Future<ProductionWipJobModel?> _singleWipJob() async {
    final scan = _singleScan;
    if (scan == null) return null;
    try {
      final result = await widget.auth.api.getJson(
        '/production/wip-jobs?active_only=true&page=1&size=100&search=${Uri.encodeQueryComponent(scan.productCode)}',
      );
      final jobs = (result['items'] as List)
          .map(
            (item) =>
                ProductionWipJobModel.fromJson(item as Map<String, dynamic>),
          )
          .where(
            (job) =>
                job.productCode == scan.productCode &&
                (scan.lotNumber == null || job.lotNumber == scan.lotNumber) &&
                job.canComplete,
          )
          .toList();
      if (jobs.length == 1) return jobs.single;
      setState(
        () => _error = jobs.isEmpty
            ? 'No active WIP job is available for this QR.'
            : 'More than one WIP job matches this QR. Open WIP Production to select it.',
      );
    } on ApiException catch (error) {
      setState(() => _error = error.message);
    }
    return null;
  }

  Future<QualityWipJobModel?> _singleQualityJob() async {
    final scan = _singleScan;
    if (scan == null) return null;
    try {
      final result = await widget.auth.api.getJson(
        '/quality/wip-jobs?page=1&size=100&search=${Uri.encodeQueryComponent(scan.productCode)}',
      );
      final jobs = (result['items'] as List)
          .map(
            (item) => QualityWipJobModel.fromJson(item as Map<String, dynamic>),
          )
          .where(
            (job) =>
                job.productCode == scan.productCode &&
                (scan.lotNumber == null || job.lotNumber == scan.lotNumber) &&
                job.canInspect,
          )
          .toList();
      if (jobs.length == 1) return jobs.single;
      setState(
        () => _error = jobs.isEmpty
            ? 'This QR is not waiting in the Quality queue.'
            : 'More than one Quality job matches this QR. Open Quality to select it.',
      );
    } on ApiException catch (error) {
      setState(() => _error = error.message);
    }
    return null;
  }

  @override
  Widget build(BuildContext context) => AppModuleScaffold(
    auth: widget.auth,
    activeModule: AppModule.scan,
    title: 'Scan QR',
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Scan Hub', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 6),
        const Text(
          'Scan product or lot labels, then select a permitted operational action.',
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _opening ? null : _scan,
          icon: const Icon(Icons.qr_code_scanner),
          label: const Text('Scan Product / Lot QR'),
        ),
        if (_error != null) ...[
          const SizedBox(height: 12),
          Text(_error!, style: const TextStyle(color: Colors.red)),
        ],
        const SizedBox(height: 16),
        if (_scans.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Text('No QR has been scanned yet.'),
            ),
          )
        else ...[
          ..._scans.map(
            (item) => Card(
              child: ListTile(
                title: Text('${item.productCode} — ${item.productName}'),
                subtitle: Text(
                  item.lotNumber == null
                      ? 'Product QR'
                      : 'Lot ${item.lotNumber}',
                ),
                trailing: IconButton(
                  tooltip: 'Remove',
                  onPressed: _opening
                      ? null
                      : () => setState(() => _scans.remove(item)),
                  icon: const Icon(Icons.close),
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Available actions',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              if (widget.auth.canAccessReceiving)
                OutlinedButton.icon(
                  onPressed: _opening ? null : _openReceiving,
                  icon: const Icon(Icons.move_to_inbox),
                  label: const Text('Receiving'),
                ),
              if (widget.auth.canAccessProduction)
                OutlinedButton.icon(
                  onPressed: _opening ? null : _openWip,
                  icon: const Icon(Icons.precision_manufacturing),
                  label: const Text('WIP Production'),
                ),
              if (widget.auth.canAccessQuality)
                OutlinedButton.icon(
                  onPressed: _opening ? null : _openQuality,
                  icon: const Icon(Icons.fact_check),
                  label: const Text('Quality'),
                ),
              if (widget.auth.canAccessDelivery)
                OutlinedButton.icon(
                  onPressed: _opening ? null : _openDelivery,
                  icon: const Icon(Icons.local_shipping),
                  label: const Text('Delivery'),
                ),
            ],
          ),
          const SizedBox(height: 12),
          const Text(
            'Receiving and Delivery retain all scanned products. WIP and Quality process one verified queue job at a time.',
          ),
        ],
      ],
    ),
  );
}
