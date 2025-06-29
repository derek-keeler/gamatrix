// Game list screen that shows filtered games in a list format

import 'package:flutter/material.dart';
import '../models/data_models.dart';
import '../services/data_store_service.dart';
import '../widgets/game_card.dart';

class GameListScreen extends StatefulWidget {
  final DataStoreService dataStoreService;
  final Set<int> selectedUserIds;
  final bool installedOnly;
  final bool includeSinglePlayer;
  final bool exclusivelyOwned;
  final Set<String> excludedPlatforms;
  final bool randomize;

  const GameListScreen({
    super.key,
    required this.dataStoreService,
    required this.selectedUserIds,
    required this.installedOnly,
    required this.includeSinglePlayer,
    required this.exclusivelyOwned,
    required this.excludedPlatforms,
    required this.randomize,
  });

  @override
  State<GameListScreen> createState() => _GameListScreenState();
}

class _GameListScreenState extends State<GameListScreen> {
  late Map<String, GameData> _filteredGames;
  late String _caption;
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _loadGames();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _loadGames() {
    if (widget.randomize) {
      final randomGame = widget.dataStoreService.getRandomGame(
        selectedUserIds: widget.selectedUserIds,
        installedOnly: widget.installedOnly,
        includeSinglePlayer: widget.includeSinglePlayer,
        exclusivelyOwned: widget.exclusivelyOwned,
        excludedPlatforms: widget.excludedPlatforms,
      );
      
      if (randomGame != null) {
        _filteredGames = {randomGame.releaseKey: randomGame};
      } else {
        _filteredGames = {};
      }
    } else {
      _filteredGames = widget.dataStoreService.getFilteredGames(
        selectedUserIds: widget.selectedUserIds,
        installedOnly: widget.installedOnly,
        includeSinglePlayer: widget.includeSinglePlayer,
        exclusivelyOwned: widget.exclusivelyOwned,
        excludedPlatforms: widget.excludedPlatforms,
      );
    }

    _caption = widget.dataStoreService.getCaption(
      _filteredGames.length,
      isRandom: widget.randomize,
    );
  }

  List<GameData> get _searchFilteredGames {
    if (_searchQuery.isEmpty) {
      return _filteredGames.values.toList();
    }

    return _filteredGames.values
        .where((game) =>
            game.title.toLowerCase().contains(_searchQuery.toLowerCase()) ||
            game.platforms.any((platform) =>
                platform.toLowerCase().contains(_searchQuery.toLowerCase())))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final dataStore = widget.dataStoreService.currentDataStore!;
    final displayGames = _searchFilteredGames;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Game List'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(60),
          child: Padding(
            padding: const EdgeInsets.all(8.0),
            child: TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                hintText: 'Search games...',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
                filled: true,
              ),
              onChanged: (value) {
                setState(() {
                  _searchQuery = value;
                });
              },
            ),
          ),
        ),
      ),
      body: Column(
        children: [
          // Caption
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _caption,
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    if (_searchQuery.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        'Showing ${displayGames.length} of ${_filteredGames.length} games',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                    const SizedBox(height: 8),
                    Text(
                      'Selected users: ${widget.selectedUserIds.map((id) => dataStore.users[id]?.username ?? 'Unknown').join(', ')}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Games list
          Expanded(
            child: displayGames.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.videogame_asset_off,
                          size: 64,
                          color: Colors.grey.shade600,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          _searchQuery.isEmpty
                              ? 'No games found matching the criteria'
                              : 'No games found matching search',
                          style: const TextStyle(fontSize: 18),
                        ),
                        if (_searchQuery.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          TextButton(
                            onPressed: () {
                              _searchController.clear();
                              setState(() {
                                _searchQuery = '';
                              });
                            },
                            child: const Text('Clear search'),
                          ),
                        ],
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(8),
                    itemCount: displayGames.length,
                    itemBuilder: (context, index) {
                      final game = displayGames[index];
                      return GameCard(
                        game: game,
                        users: dataStore.users,
                        selectedUserIds: widget.selectedUserIds,
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}