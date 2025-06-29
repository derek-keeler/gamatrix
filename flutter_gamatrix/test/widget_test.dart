// Basic test for the Flutter Gamatrix app

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_gamatrix/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const FlutterGamatrixApp());

    // Verify that the app title appears
    expect(find.text('Flutter Gamatrix'), findsOneWidget);
  });
}