// Unit tests for data models

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_gamatrix/models/data_models.dart';

void main() {
  group('GameData', () {
    test('should create GameData from JSON', () {
      final json = {
        'release_key': 'test_game',
        'title': 'Test Game',
        'slug': 'test-game',
        'platforms': ['steam'],
        'owners': [1, 2],
        'installed': [1],
        'igdb_key': 'test',
        'multiplayer': true,
        'max_players': 4,
      };

      final gameData = GameData.fromJson(json);

      expect(gameData.releaseKey, 'test_game');
      expect(gameData.title, 'Test Game');
      expect(gameData.multiplayer, true);
      expect(gameData.maxPlayers, 4);
      expect(gameData.owners, [1, 2]);
      expect(gameData.installed, [1]);
    });

    test('should convert GameData to JSON', () {
      final gameData = GameData(
        releaseKey: 'test_game',
        title: 'Test Game',
        slug: 'test-game',
        platforms: ['steam'],
        owners: [1, 2],
        installed: [1],
        igdbKey: 'test',
        multiplayer: true,
        maxPlayers: 4,
      );

      final json = gameData.toJson();

      expect(json['release_key'], 'test_game');
      expect(json['title'], 'Test Game');
      expect(json['multiplayer'], true);
      expect(json['max_players'], 4);
    });
  });

  group('UserData', () {
    test('should create UserData from JSON', () {
      final json = {
        'user_id': 123,
        'username': 'testuser',
        'db_filename': 'test.db',
        'db_mtime': '2024-01-01 12:00:00',
        'total_games': 100,
        'installed_games': 25,
      };

      final userData = UserData.fromJson(json);

      expect(userData.userId, 123);
      expect(userData.username, 'testuser');
      expect(userData.totalGames, 100);
      expect(userData.installedGames, 25);
    });
  });

  group('DataStore', () {
    test('should create DataStore from JSON', () {
      final json = {
        'version': '1.0',
        'last_updated': '2024-01-01T12:00:00',
        'users': {
          '123': {
            'user_id': 123,
            'username': 'testuser',
            'db_filename': 'test.db',
            'db_mtime': '2024-01-01 12:00:00',
            'total_games': 100,
            'installed_games': 25,
          }
        },
        'games': {
          'test_game': {
            'release_key': 'test_game',
            'title': 'Test Game',
            'slug': 'test-game',
            'platforms': ['steam'],
            'owners': [123],
            'installed': [123],
            'igdb_key': 'test',
            'multiplayer': false,
          }
        }
      };

      final dataStore = DataStore.fromJson(json);

      expect(dataStore.version, '1.0');
      expect(dataStore.users.length, 1);
      expect(dataStore.games.length, 1);
      expect(dataStore.users[123]?.username, 'testuser');
      expect(dataStore.games['test_game']?.title, 'Test Game');
    });
  });
}