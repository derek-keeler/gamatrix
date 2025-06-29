// Game grid screen that shows games in a grid format with ownership indicators

import 'package:flutter/material.dart';
import '../models/data_models.dart';
import '../services/data_store_service.dart';

class GameGridScreen extends StatefulWidget {
  final DataStoreService dataStoreService;
  final Set<int> selectedUserIds;
  final bool installedOnly;
  final bool includeSinglePlayer;
  final bool exclusivelyOwned;
  final Set<String> excludedPlatforms;

  const GameGridScreen({
    super.key,
    required this.dataStoreService,
    required this.selectedUserIds,
    required this.installedOnly,
    required this.includeSinglePlayer,
    required this.exclusivelyOwned,
    required this.excludedPlatforms,
  });

  @override
  State<GameGridScreen> createState() => _GameGridScreenState();
}

class _GameGridScreenState extends State<GameGridScreen> {
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
    _filteredGames = widget.dataStoreService.getFilteredGames(
      selectedUserIds: widget.selectedUserIds,
      installedOnly: widget.installedOnly,
      includeSinglePlayer: widget.includeSinglePlayer,
      exclusivelyOwned: widget.exclusivelyOwned,
      excludedPlatforms: widget.excludedPlatforms,
    );

    _caption = widget.dataStoreService.getCaption(_filteredGames.length);
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
    final selectedUsers = widget.selectedUserIds
        .map((id) => dataStore.users[id])
        .where((user) => user != null)
        .cast<UserData>()
        .toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Game Grid'),
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
          // Caption and user header
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
                    const SizedBox(height: 16),
                    // User header row
                    Row(
                      children: [
                        const SizedBox(width: 200), // Space for game title
                        ...selectedUsers.map((user) => 
                          Expanded(
                            child: Center(
                              child: Column(
                                children: [
                                  Text(
                                    user.username,
                                    style: const TextStyle(fontWeight: FontWeight.bold),
                                  ),
                                  Text(
                                    '${user.totalGames} games',
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Games grid
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
                      return Card(
                        margin: const EdgeInsets.symmetric(vertical: 2),
                        child: Padding(
                          padding: const EdgeInsets.all(8),
                          child: Row(
                            children: [
                              // Game title and info
                              SizedBox(
                                width: 200,
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      game.title,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.bold,
                                        fontSize: 14,
                                      ),
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    const SizedBox(height: 4),
                                    Wrap(
                                      spacing: 4,
                                      children: game.platforms.map((platform) =>
                                        Chip(
                                          label: Text(
                                            platform.toUpperCase(),
                                            style: const TextStyle(fontSize: 10),
                                          ),
                                          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                          visualDensity: VisualDensity.compact,
                                        ),
                                      ).toList(),
                                    ),
                                    if (game.multiplayer) ...[
                                      const SizedBox(height: 2),
                                      Text(
                                        game.maxPlayers != null
                                            ? 'Max ${game.maxPlayers} players'
                                            : 'Multiplayer',
                                        style: const TextStyle(
                                          fontSize: 10,
                                          color: Colors.teal,
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                              
                              // Ownership grid
                              ...selectedUsers.map((user) => 
                                Expanded(
                                  child: Container(
                                    height: 40,
                                    margin: const EdgeInsets.symmetric(horizontal: 2),
                                    decoration: BoxDecoration(
                                      color: game.owners.contains(user.userId)
                                          ? Colors.green.shade600
                                          : Colors.red.shade600,
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Center(
                                      child: game.owners.contains(user.userId)
                                          ? game.installed.contains(user.userId)
                                              ? const Icon(
                                                  Icons.check_circle,
                                                  color: Colors.white,
                                                  size: 20,
                                                )
                                              : const Icon(
                                                  Icons.circle_outlined,
                                                  color: Colors.white,
                                                  size: 20,
                                                )
                                          : const Icon(
                                              Icons.close,
                                              color: Colors.white,
                                              size: 20,
                                            ),
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}