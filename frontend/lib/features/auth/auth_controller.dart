import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/api_client.dart';
import '../users/user_model.dart';

class PurchasingAccess {
  const PurchasingAccess({
    required this.canAccess,
    required this.isPic,
    required this.isHead,
    required this.canReview,
  });

  const PurchasingAccess.denied()
    : canAccess = false,
      isPic = false,
      isHead = false,
      canReview = false;

  factory PurchasingAccess.fromJson(Map<String, dynamic> json) {
    return PurchasingAccess(
      canAccess: json['can_access'] == true,
      isPic: json['is_pic'] == true,
      isHead: json['is_head'] == true,
      canReview: json['can_review'] == true,
    );
  }

  final bool canAccess;
  final bool isPic;
  final bool isHead;
  final bool canReview;
}

typedef SalesOrderAccess = PurchasingAccess;
typedef ReceivingAccess = PurchasingAccess;
typedef WarehouseAccess = PurchasingAccess;
typedef ProductionAccess = PurchasingAccess;
typedef QualityAccess = PurchasingAccess;

class AuthController extends ChangeNotifier {
  AuthController(this.api);

  final ApiClient api;
  UserModel? currentUser;
  PurchasingAccess purchasingAccess = const PurchasingAccess.denied();
  SalesOrderAccess salesOrderAccess = const SalesOrderAccess.denied();
  ReceivingAccess receivingAccess = const ReceivingAccess.denied();
  WarehouseAccess warehouseAccess = const WarehouseAccess.denied();
  ProductionAccess productionAccess = const ProductionAccess.denied();
  QualityAccess qualityAccess = const QualityAccess.denied();
  bool isLoading = false;
  String? error;

  bool get isAuthenticated => currentUser != null && api.token != null;
  bool get canAccessPurchasing => purchasingAccess.canAccess;
  bool get canAccessSalesOrder => salesOrderAccess.canAccess;
  bool get canAccessReceiving => receivingAccess.canAccess;
  bool get canAccessWarehouse => warehouseAccess.canAccess;
  bool get canAccessProduction => productionAccess.canAccess;
  bool get canAccessQuality => qualityAccess.canAccess;
  bool get canAccessFinishGood => canAccessWarehouse;
  bool get canAccessDelivery =>
      currentUser?.role.trim().toLowerCase() == 'courier' ||
      currentUser?.accessLevel == 'administrator';

  Future<void> restoreSession() async {
    final preferences = await SharedPreferences.getInstance();
    final token = preferences.getString('access_token');
    if (token == null) return;
    api.token = token;
    try {
      currentUser = UserModel.fromJson(await api.getJson('/auth/me'));
      await refreshPurchasingAccess(notify: false);
      await refreshSalesOrderAccess(notify: false);
      await refreshReceivingAccess(notify: false);
      await refreshWarehouseAccess(notify: false);
      await refreshProductionAccess(notify: false);
      await refreshQualityAccess(notify: false);
    } catch (_) {
      api.token = null;
      await preferences.remove('access_token');
    }
  }

  Future<bool> login(String email, String password) async {
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final result = await api.postJson('/auth/login', {
        'email': email.trim(),
        'password': password,
      });
      api.token = result['access_token'] as String;
      currentUser = UserModel.fromJson(await api.getJson('/auth/me'));
      await refreshPurchasingAccess(notify: false);
      await refreshSalesOrderAccess(notify: false);
      await refreshReceivingAccess(notify: false);
      await refreshWarehouseAccess(notify: false);
      await refreshProductionAccess(notify: false);
      await refreshQualityAccess(notify: false);
      final preferences = await SharedPreferences.getInstance();
      await preferences.setString('access_token', api.token!);
      return true;
    } on ApiException catch (exception) {
      error = exception.message;
      return false;
    } catch (_) {
      error = 'Tidak dapat terhubung ke server';
      return false;
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    api.token = null;
    currentUser = null;
    purchasingAccess = const PurchasingAccess.denied();
    salesOrderAccess = const SalesOrderAccess.denied();
    receivingAccess = const ReceivingAccess.denied();
    warehouseAccess = const WarehouseAccess.denied();
    productionAccess = const ProductionAccess.denied();
    qualityAccess = const QualityAccess.denied();
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove('access_token');
    notifyListeners();
  }

  Future<PurchasingAccess> refreshPurchasingAccess({bool notify = true}) async {
    purchasingAccess = PurchasingAccess.fromJson(
      await api.getJson('/module-access/purchasing'),
    );
    if (notify) notifyListeners();
    return purchasingAccess;
  }

  Future<SalesOrderAccess> refreshSalesOrderAccess({bool notify = true}) async {
    salesOrderAccess = SalesOrderAccess.fromJson(
      await api.getJson('/module-access/sales-order'),
    );
    if (notify) notifyListeners();
    return salesOrderAccess;
  }

  Future<ReceivingAccess> refreshReceivingAccess({bool notify = true}) async {
    receivingAccess = ReceivingAccess.fromJson(
      await api.getJson('/module-access/receiving'),
    );
    if (notify) notifyListeners();
    return receivingAccess;
  }

  Future<WarehouseAccess> refreshWarehouseAccess({bool notify = true}) async {
    warehouseAccess = WarehouseAccess.fromJson(
      await api.getJson('/module-access/warehouse'),
    );
    if (notify) notifyListeners();
    return warehouseAccess;
  }

  Future<ProductionAccess> refreshProductionAccess({bool notify = true}) async {
    productionAccess = ProductionAccess.fromJson(
      await api.getJson('/module-access/production'),
    );
    if (notify) notifyListeners();
    return productionAccess;
  }

  Future<QualityAccess> refreshQualityAccess({bool notify = true}) async {
    qualityAccess = QualityAccess.fromJson(
      await api.getJson('/module-access/quality'),
    );
    if (notify) notifyListeners();
    return qualityAccess;
  }

  Future<void> refreshModuleAccess() async {
    await refreshPurchasingAccess(notify: false);
    await refreshSalesOrderAccess(notify: false);
    await refreshReceivingAccess(notify: false);
    await refreshWarehouseAccess(notify: false);
    await refreshProductionAccess(notify: false);
    await refreshQualityAccess(notify: false);
    notifyListeners();
  }
}
