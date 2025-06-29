// Service for ingesting and managing Gamatrix data store files
// This service handles loading data store JSON files and filtering games

import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/data_models.dart';

class DataStoreService {
  static const String _dataStoreKey = 'data_store_path';
  static const String _lastDataStoreKey = 'last_data_store';
  
  DataStore? _currentDataStore;
  String? _dataStorePath;

  /// Get current data store, if loaded
  DataStore? get currentDataStore => _currentDataStore;

  /// Check if data store is loaded
  bool get isDataStoreLoaded => _currentDataStore != null;

  /// Load data store from a file path
  Future<DataStore?> loadDataStore(String filePath) async {
    try {
      final file = File(filePath);
      if (!await file.exists()) {
        debugPrint('Data store file does not exist: $filePath');
        return null;
      }

      final contents = await file.readAsString();
      final jsonData = jsonDecode(contents) as Map<String, dynamic>;
      
      _currentDataStore = DataStore.fromJson(jsonData);
      _dataStorePath = filePath;
      
      // Save the path for future use
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_dataStoreKey, filePath);
      await prefs.setString(_lastDataStoreKey, contents);
      
      debugPrint('Data store loaded successfully from: $filePath');
      debugPrint('Found ${_currentDataStore!.users.length} users and ${_currentDataStore!.games.length} games');
      
      return _currentDataStore;
    } catch (e) {
      debugPrint('Error loading data store: $e');
      return null;
    }
  }

  /// Load data store from previously saved path
  Future<DataStore?> loadSavedDataStore() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedPath = prefs.getString(_dataStoreKey);
      
      if (savedPath != null) {
        return await loadDataStore(savedPath);
      }
      
      debugPrint('No saved data store path found');
      return null;
    } catch (e) {
      debugPrint('Error loading saved data store: $e');
      return null;
    }
  }

  /// Get filtered games based on user selection and filters
  Map<String, GameData> getFilteredGames({
    required Set<int> selectedUserIds,
    bool installedOnly = false,
    bool includeSinglePlayer = false,
    bool exclusivelyOwned = false,
    Set<String> excludedPlatforms = const {},
  }) {
    if (_currentDataStore == null) {
      return {};
    }

    final filteredGames = <String, GameData>{};

    for (final entry in _currentDataStore!.games.entries) {
      final game = entry.value;
      
      // Check if any selected users own this game
      final ownersInSelection = game.owners.where((userId) => selectedUserIds.contains(userId)).toSet();
      if (ownersInSelection.isEmpty) {
        continue;
      }

      // If exclusively owned is enabled, check that no unselected users own the game
      if (exclusivelyOwned) {
        final unselectedOwners = game.owners.where((userId) => !selectedUserIds.contains(userId));
        if (unselectedOwners.isNotEmpty) {
          continue;
        }
      }

      // Check multiplayer filter
      if (!includeSinglePlayer && !game.multiplayer) {
        continue;
      }

      // Check installed only filter
      if (installedOnly) {
        final installedInSelection = game.installed.where((userId) => selectedUserIds.contains(userId));
        if (installedInSelection.length != selectedUserIds.length) {
          continue;
        }
      }

      // Check platform exclusions
      if (excludedPlatforms.isNotEmpty) {
        final gameHasExcludedPlatform = game.platforms.any((platform) => excludedPlatforms.contains(platform));
        if (gameHasExcludedPlatform) {
          continue;
        }
      }

      filteredGames[entry.key] = game;
    }

    return filteredGames;
  }

  /// Get a random game from filtered results
  GameData? getRandomGame({
    required Set<int> selectedUserIds,
    bool installedOnly = false,
    bool includeSinglePlayer = false,
    bool exclusivelyOwned = false,
    Set<String> excludedPlatforms = const {},
  }) {
    final filteredGames = getFilteredGames(
      selectedUserIds: selectedUserIds,
      installedOnly: installedOnly,
      includeSinglePlayer: includeSinglePlayer,
      exclusivelyOwned: exclusivelyOwned,
      excludedPlatforms: excludedPlatforms,
    );

    if (filteredGames.isEmpty) {
      return null;
    }

    final keys = filteredGames.keys.toList();
    keys.shuffle();
    return filteredGames[keys.first];
  }

  /// Get caption text similar to the Python version
  String getCaption(int gameCount, {bool isRandom = false}) {
    if (isRandom) {
      return 'Random game selected';
    }
    
    if (gameCount == 0) {
      return 'No games found matching the criteria';
    } else if (gameCount == 1) {
      return '1 game found';
    } else {
      return '$gameCount games found';
    }
  }

  /// Create a sample data store for testing/demo purposes
  Future<String> createSampleDataStore() async {
    final directory = await getApplicationDocumentsDirectory();
    final samplePath = '${directory.path}/sample_data_store.json';
    
    final sampleData = DataStore(
      users: {
        12345: UserData(
          userId: 12345,
          username: 'Alice',
          dbFilename: 'alice-galaxy-2.0.db',
          dbMtime: '2024-01-01 12:00:00',
          totalGames: 150,
          installedGames: 25,
        ),
        67890: UserData(
          userId: 67890,
          username: 'Bob',
          dbFilename: 'bob-galaxy-2.0.db',
          dbMtime: '2024-01-01 13:00:00',
          totalGames: 200,
          installedGames: 30,
        ),
      },
      games: {
        'witcher3_steam': GameData(
          releaseKey: 'witcher3_steam',
          title: 'The Witcher 3: Wild Hunt',
          slug: 'witcher-3-wild-hunt',
          platforms: ['steam'],
          owners: [12345, 67890],
          installed: [12345],
          igdbKey: 'witcher3',
          multiplayer: false,
          maxPlayers: 1,
        ),
        'portal2_steam': GameData(
          releaseKey: 'portal2_steam',
          title: 'Portal 2',
          slug: 'portal-2',
          platforms: ['steam'],
          owners: [12345, 67890],
          installed: [12345, 67890],
          igdbKey: 'portal2',
          multiplayer: true,
          maxPlayers: 2,
        ),
        'minecraft_gog': GameData(
          releaseKey: 'minecraft_gog',
          title: 'Minecraft',
          slug: 'minecraft',
          platforms: ['gog'],
          owners: [67890],
          installed: [67890],
          igdbKey: 'minecraft',
          multiplayer: true,
          maxPlayers: null,
        ),
      },
      lastUpdated: DateTime.now().toIso8601String(),
      version: '1.0',
    );

    final file = File(samplePath);
    await file.writeAsString(jsonEncode(sampleData.toJson()));
    
    debugPrint('Sample data store created at: $samplePath');
    return samplePath;
  }

  /// Clear current data store
  void clearDataStore() {
    _currentDataStore = null;
    _dataStorePath = null;
  }

  /// Get the list of available platforms from the current data store
  Set<String> getAvailablePlatforms() {
    if (_currentDataStore == null) {
      return {};
    }

    final platforms = <String>{};
    for (final game in _currentDataStore!.games.values) {
      platforms.addAll(game.platforms);
    }
    return platforms;
  }
}