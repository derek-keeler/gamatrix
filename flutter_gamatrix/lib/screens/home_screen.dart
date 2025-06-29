// Home screen that mirrors the functionality of the original Gamatrix web interface

import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../models/data_models.dart';
import '../services/data_store_service.dart';
import 'game_list_screen.dart';
import 'game_grid_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final DataStoreService _dataStoreService = DataStoreService();
  
  // UI state
  int _selectedViewMode = 0; // 0: game list, 1: game grid
  final Set<int> _selectedUserIds = {};
  bool _installedOnly = false;
  bool _includeSinglePlayer = false;
  bool _exclusivelyOwned = false;
  bool _randomize = false;
  final Set<String> _excludedPlatforms = {};
  
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadSavedDataStore();
  }

  Future<void> _loadSavedDataStore() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final dataStore = await _dataStoreService.loadSavedDataStore();
      if (dataStore == null) {
        // Create sample data store for demo
        final samplePath = await _dataStoreService.createSampleDataStore();
        await _dataStoreService.loadDataStore(samplePath);
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error loading data store: $e';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _selectDataStoreFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['json'],
        dialogTitle: 'Select Gamatrix Data Store File',
      );

      if (result != null && result.files.single.path != null) {
        setState(() {
          _isLoading = true;
          _errorMessage = null;
        });

        final dataStore = await _dataStoreService.loadDataStore(result.files.single.path!);
        if (dataStore == null) {
          setState(() {
            _errorMessage = 'Failed to load data store file';
          });
        } else {
          // Clear selections when new data store is loaded
          _selectedUserIds.clear();
          _excludedPlatforms.clear();
        }

        setState(() {
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Error selecting file: $e';
      });
    }
  }

  void _showResults() {
    if (_selectedUserIds.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select at least one user')),
      );
      return;
    }

    if (_selectedViewMode == 0) {
      // Game list view
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => GameListScreen(
            dataStoreService: _dataStoreService,
            selectedUserIds: _selectedUserIds,
            installedOnly: _installedOnly,
            includeSinglePlayer: _includeSinglePlayer,
            exclusivelyOwned: _exclusivelyOwned,
            excludedPlatforms: _excludedPlatforms,
            randomize: _randomize,
          ),
        ),
      );
    } else {
      // Game grid view
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => GameGridScreen(
            dataStoreService: _dataStoreService,
            selectedUserIds: _selectedUserIds,
            installedOnly: _installedOnly,
            includeSinglePlayer: _includeSinglePlayer,
            exclusivelyOwned: _exclusivelyOwned,
            excludedPlatforms: _excludedPlatforms,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final dataStore = _dataStoreService.currentDataStore;
    final availablePlatforms = _dataStoreService.getAvailablePlatforms().toList()..sort();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Flutter Gamatrix'),
        actions: [
          IconButton(
            icon: const Icon(Icons.folder_open),
            onPressed: _selectDataStoreFile,
            tooltip: 'Load Data Store File',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _buildBody(dataStore, availablePlatforms),
    );
  }

  Widget _buildBody(DataStore? dataStore, List<String> availablePlatforms) {
    if (_errorMessage != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red.shade300),
            const SizedBox(height: 16),
            Text(
              _errorMessage!,
              style: const TextStyle(fontSize: 16),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _selectDataStoreFile,
              child: const Text('Select Data Store File'),
            ),
          ],
        ),
      );
    }

    if (dataStore == null) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.storage, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text(
              'No data store loaded',
              style: TextStyle(fontSize: 18),
            ),
            SizedBox(height: 8),
            Text(
              'Please select a Gamatrix data store JSON file',
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Data store info
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Data Store Info',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  Text('Users: ${dataStore.users.length}'),
                  Text('Games: ${dataStore.games.length}'),
                  Text('Last Updated: ${dataStore.lastUpdated}'),
                  Text('Version: ${dataStore.version}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // View mode selection
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'View Mode',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  RadioListTile<int>(
                    title: const Text('Game List'),
                    value: 0,
                    groupValue: _selectedViewMode,
                    onChanged: (value) {
                      setState(() {
                        _selectedViewMode = value!;
                      });
                    },
                  ),
                  RadioListTile<int>(
                    title: const Text('Game Grid'),
                    value: 1,
                    groupValue: _selectedViewMode,
                    onChanged: (value) {
                      setState(() {
                        _selectedViewMode = value!;
                      });
                    },
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // User selection
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Select Users',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  ...dataStore.users.values.map((user) => CheckboxListTile(
                        title: Text(user.username),
                        subtitle: Text('DB: ${user.dbMtime}'),
                        value: _selectedUserIds.contains(user.userId),
                        onChanged: (bool? value) {
                          setState(() {
                            if (value == true) {
                              _selectedUserIds.add(user.userId);
                            } else {
                              _selectedUserIds.remove(user.userId);
                            }
                          });
                        },
                      )),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Platform exclusions
          if (availablePlatforms.isNotEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Exclude Platforms',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      children: availablePlatforms.map((platform) => 
                        CheckboxListTile(
                          title: Text(platform.toUpperCase()),
                          controlAffinity: ListTileControlAffinity.leading,
                          value: _excludedPlatforms.contains(platform),
                          onChanged: (bool? value) {
                            setState(() {
                              if (value == true) {
                                _excludedPlatforms.add(platform);
                              } else {
                                _excludedPlatforms.remove(platform);
                              }
                            });
                          },
                        ),
                      ).toList(),
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 16),

          // Options
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Options',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  CheckboxListTile(
                    title: const Text('Exclusively owned'),
                    subtitle: const Text('Games owned by selected users only'),
                    value: _exclusivelyOwned,
                    onChanged: (bool? value) {
                      setState(() {
                        _exclusivelyOwned = value ?? false;
                      });
                    },
                  ),
                  CheckboxListTile(
                    title: const Text('Installed only'),
                    subtitle: const Text('Only show games installed by all selected users'),
                    value: _installedOnly,
                    onChanged: (bool? value) {
                      setState(() {
                        _installedOnly = value ?? false;
                      });
                    },
                  ),
                  CheckboxListTile(
                    title: const Text('Include single-player'),
                    value: _includeSinglePlayer,
                    onChanged: (bool? value) {
                      setState(() {
                        _includeSinglePlayer = value ?? false;
                      });
                    },
                  ),
                  CheckboxListTile(
                    title: const Text('Pick a random game'),
                    value: _randomize,
                    onChanged: (bool? value) {
                      setState(() {
                        _randomize = value ?? false;
                      });
                    },
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // Show results button
          Center(
            child: ElevatedButton(
              onPressed: _showResults,
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(120, 50),
                textStyle: const TextStyle(fontSize: 20),
              ),
              child: const Text("Giv'er"),
            ),
          ),
        ],
      ),
    );
  }
}