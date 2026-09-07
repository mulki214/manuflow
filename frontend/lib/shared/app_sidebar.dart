import 'package:flutter/material.dart';

import '../features/auth/auth_controller.dart';
import 'mobile_product_scanner.dart';

enum AppModule {
  dashboard(Icons.dashboard_outlined, 'Dashboard'),
  user(Icons.people_outline, 'User'),
  masterData(Icons.dataset_outlined, 'Master Data'),
  salesOrder(Icons.shopping_cart_outlined, 'Sales Order'),
  purchasing(Icons.shopping_bag_outlined, 'Purchasing'),
  receiving(Icons.move_to_inbox_outlined, 'Receiving'),
  warehouse(Icons.warehouse_outlined, 'Warehouse'),
  production(Icons.precision_manufacturing_outlined, 'Production'),
  quality(Icons.fact_check_outlined, 'Quality'),
  finishGood(Icons.inventory_2_outlined, 'Finish Good'),
  delivery(Icons.local_shipping_outlined, 'Delivery'),
  reporting(Icons.bar_chart_outlined, 'Reporting'),
  scan(Icons.qr_code_scanner_outlined, 'Scan QR');

  const AppModule(this.icon, this.label);

  final IconData icon;
  final String label;
}

class AppSidebar extends StatelessWidget {
  const AppSidebar({
    super.key,
    required this.auth,
    required this.activeModule,
    required this.onModuleSelected,
    this.onChangePassword,
  });

  final AuthController auth;
  final AppModule activeModule;
  final ValueChanged<AppModule> onModuleSelected;
  final VoidCallback? onChangePassword;

  @override
  Widget build(BuildContext context) {
    final showScanHub =
        supportsMobileProductScanner && MediaQuery.sizeOf(context).width < 1000;
    return Container(
      width: 250,
      color: const Color(0xFF101828),
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 16),
      child: Column(
        children: [
          const ListTile(
            leading: Icon(Icons.factory_outlined, color: Color(0xFF84CAFF)),
            title: Text(
              'MANUFLOW',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.2,
              ),
            ),
          ),
          const SizedBox(height: 22),
          Expanded(
            child: ListView(
              children: AppModule.values
                  .where(
                    (module) =>
                        module != AppModule.user &&
                        switch (module) {
                          AppModule.purchasing => auth.canAccessPurchasing,
                          AppModule.salesOrder => auth.canAccessSalesOrder,
                          AppModule.receiving => auth.canAccessReceiving,
                          AppModule.warehouse => auth.canAccessWarehouse,
                          AppModule.production => auth.canAccessProduction,
                          AppModule.quality => auth.canAccessQuality,
                          AppModule.finishGood => auth.canAccessFinishGood,
                          AppModule.delivery => auth.canAccessDelivery,
                          AppModule.scan => showScanHub,
                          _ => true,
                        },
                  )
                  .map((module) => _navigationItem(module))
                  .toList(),
            ),
          ),
          const Divider(color: Color(0xFF344054)),
          if (onChangePassword != null)
            ListTile(
              leading: const Icon(
                Icons.password_outlined,
                color: Color(0xFF98A2B3),
              ),
              title: const Text(
                'Change Password',
                style: TextStyle(color: Color(0xFFD0D5DD), fontSize: 13),
              ),
              onTap: onChangePassword,
            ),
          ListTile(
            leading: CircleAvatar(
              child: Text(auth.currentUser?.initials ?? 'U'),
            ),
            title: Text(
              auth.currentUser?.fullName ?? '',
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: Colors.white, fontSize: 14),
            ),
            subtitle: Text(
              auth.currentUser?.role ?? '',
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: Color(0xFF98A2B3), fontSize: 12),
            ),
            trailing: IconButton(
              onPressed: auth.logout,
              tooltip: 'Keluar',
              icon: const Icon(Icons.logout, color: Color(0xFF98A2B3)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _navigationItem(AppModule module) {
    final selected = module == activeModule;
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: ListTile(
        selected: selected,
        selectedTileColor: const Color(0xFF344054),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        leading: Icon(
          module.icon,
          color: selected ? Colors.white : const Color(0xFF98A2B3),
        ),
        title: Text(
          module.label,
          style: TextStyle(
            color: selected ? Colors.white : const Color(0xFFD0D5DD),
            fontSize: 14,
          ),
        ),
        onTap: selected ? null : () => onModuleSelected(module),
      ),
    );
  }
}
