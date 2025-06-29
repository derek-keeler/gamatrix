// Data models for Gamatrix Flutter app
// These models mirror the Python data structures from data_store_helper.py

import 'dart:convert';

/// Represents a single game with all its metadata
class GameData {
  final String releaseKey;
  final String title;
  final String slug;
  final List<String> platforms;
  final List<int> owners; // User IDs who own this game
  final List<int> installed; // User IDs who have this game installed
  final String igdbKey;
  final bool multiplayer;
  final int? maxPlayers;
  final String? comment;
  final String? url;

  GameData({
    required this.releaseKey,
    required this.title,
    required this.slug,
    required this.platforms,
    required this.owners,
    required this.installed,
    required this.igdbKey,
    this.multiplayer = false,
    this.maxPlayers,
    this.comment,
    this.url,
  });

  factory GameData.fromJson(Map<String, dynamic> json) {
    return GameData(
      releaseKey: json['release_key'] as String,
      title: json['title'] as String,
      slug: json['slug'] as String,
      platforms: List<String>.from(json['platforms'] as List),
      owners: List<int>.from(json['owners'] as List),
      installed: List<int>.from(json['installed'] as List),
      igdbKey: json['igdb_key'] as String,
      multiplayer: json['multiplayer'] as bool? ?? false,
      maxPlayers: json['max_players'] as int?,
      comment: json['comment'] as String?,
      url: json['url'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'release_key': releaseKey,
      'title': title,
      'slug': slug,
      'platforms': platforms,
      'owners': owners,
      'installed': installed,
      'igdb_key': igdbKey,
      'multiplayer': multiplayer,
      'max_players': maxPlayers,
      'comment': comment,
      'url': url,
    };
  }
}

/// Represents a user and their game library metadata
class UserData {
  final int userId;
  final String username;
  final String dbFilename;
  final String dbMtime;
  final int totalGames;
  final int installedGames;

  UserData({
    required this.userId,
    required this.username,
    required this.dbFilename,
    required this.dbMtime,
    required this.totalGames,
    required this.installedGames,
  });

  factory UserData.fromJson(Map<String, dynamic> json) {
    return UserData(
      userId: json['user_id'] as int,
      username: json['username'] as String,
      dbFilename: json['db_filename'] as String,
      dbMtime: json['db_mtime'] as String,
      totalGames: json['total_games'] as int,
      installedGames: json['installed_games'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'username': username,
      'db_filename': dbFilename,
      'db_mtime': dbMtime,
      'total_games': totalGames,
      'installed_games': installedGames,
    };
  }
}

/// Complete data store containing all user and game information
class DataStore {
  final Map<int, UserData> users;
  final Map<String, GameData> games; // Keyed by release_key
  final String lastUpdated;
  final String version;

  DataStore({
    required this.users,
    required this.games,
    required this.lastUpdated,
    this.version = '1.0',
  });

  factory DataStore.fromJson(Map<String, dynamic> json) {
    // Convert users from JSON
    final usersJson = json['users'] as Map<String, dynamic>;
    final users = <int, UserData>{};
    for (final entry in usersJson.entries) {
      final userId = int.parse(entry.key);
      users[userId] = UserData.fromJson(entry.value as Map<String, dynamic>);
    }

    // Convert games from JSON
    final gamesJson = json['games'] as Map<String, dynamic>;
    final games = <String, GameData>{};
    for (final entry in gamesJson.entries) {
      games[entry.key] = GameData.fromJson(entry.value as Map<String, dynamic>);
    }

    return DataStore(
      users: users,
      games: games,
      lastUpdated: json['last_updated'] as String,
      version: json['version'] as String? ?? '1.0',
    );
  }

  Map<String, dynamic> toJson() {
    final usersJson = <String, dynamic>{};
    for (final entry in users.entries) {
      usersJson[entry.key.toString()] = entry.value.toJson();
    }

    final gamesJson = <String, dynamic>{};
    for (final entry in games.entries) {
      gamesJson[entry.key] = entry.value.toJson();
    }

    return {
      'users': usersJson,
      'games': gamesJson,
      'last_updated': lastUpdated,
      'version': version,
    };
  }
}