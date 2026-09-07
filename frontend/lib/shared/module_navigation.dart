import 'package:flutter/material.dart';

import '../features/auth/auth_controller.dart';
import '../features/dashboard/dashboard_page.dart';
import '../features/delivery/delivery_page.dart';
import '../features/finish_good/finish_good_page.dart';
import '../features/master_data/master_data_page.dart';
import '../features/production/production_page.dart';
import '../features/purchasing/purchasing_page.dart';
import '../features/quality/quality_page.dart';
import '../features/receiving/receiving_page.dart';
import '../features/reporting/reporting_page.dart';
import '../features/sales_order/sales_order_page.dart';
import '../features/scan/scan_hub_page.dart';
import '../features/warehouse/warehouse_page.dart';
import 'app_sidebar.dart';

/// Shared navigation policy for every operational sidebar.
void navigateToModule(
  BuildContext context,
  AuthController auth,
  AppModule module, {
  AppModule? activeModule,
}) {
  if (module == activeModule) return;
  if (module == AppModule.user) {
    Navigator.of(context).popUntil((route) => route.isFirst);
    return;
  }
  final Widget? page = switch (module) {
    AppModule.dashboard => DashboardPage(auth: auth),
    AppModule.masterData => MasterDataPage(auth: auth),
    AppModule.salesOrder when auth.canAccessSalesOrder => SalesOrderPage(
      auth: auth,
    ),
    AppModule.purchasing when auth.canAccessPurchasing => PurchasingPage(
      auth: auth,
    ),
    AppModule.receiving when auth.canAccessReceiving => ReceivingPage(
      auth: auth,
    ),
    AppModule.warehouse when auth.canAccessWarehouse => WarehousePage(
      auth: auth,
    ),
    AppModule.production when auth.canAccessProduction => ProductionPage(
      auth: auth,
    ),
    AppModule.quality when auth.canAccessQuality => QualityPage(auth: auth),
    AppModule.finishGood when auth.canAccessFinishGood => FinishGoodPage(
      auth: auth,
    ),
    AppModule.delivery when auth.canAccessDelivery => DeliveryPage(auth: auth),
    AppModule.reporting => ReportingPage(auth: auth),
    AppModule.scan => ScanHubPage(auth: auth),
    _ => null,
  };
  if (page != null) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));
  }
}
