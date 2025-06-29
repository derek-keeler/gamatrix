// Reusable game card widget for displaying game information

import 'package:flutter/material.dart';
import '../models/data_models.dart';

class GameCard extends StatelessWidget {
  final GameData game;
  final Map<int, UserData> users;
  final Set<int> selectedUserIds;

  const GameCard({
    super.key,
    required this.game,
    required this.users,
    required this.selectedUserIds,
  });

  @override
  Widget build(BuildContext context) {
    final installedUsers = game.installed
        .where((userId) => selectedUserIds.contains(userId))
        .map((userId) => users[userId]?.username ?? 'Unknown')
        .toList();
    
    final allUsersHaveInstalled = installedUsers.length == selectedUserIds.length;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
      child: ExpansionTile(
        title: Text(
          game.title,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: game.multiplayer ? null : Colors.grey.shade400,
          ),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Platforms
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
            const SizedBox(height: 4),
            
            // Multiplayer info
            if (game.multiplayer) ...[
              Row(
                children: [
                  const Icon(Icons.group, size: 16, color: Colors.teal),
                  const SizedBox(width: 4),
                  Text(
                    game.maxPlayers != null
                        ? 'Max ${game.maxPlayers} players'
                        : 'Multiplayer',
                    style: const TextStyle(
                      color: Colors.teal,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ] else ...[
              const Row(
                children: [
                  Icon(Icons.person, size: 16, color: Colors.grey),
                  SizedBox(width: 4),
                  Text(
                    'Single-player',
                    style: TextStyle(
                      color: Colors.grey,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 4),
            
            // Installation status
            Row(
              children: [
                Icon(
                  allUsersHaveInstalled
                      ? Icons.check_circle
                      : installedUsers.isNotEmpty
                          ? Icons.check_circle_outline
                          : Icons.circle_outlined,
                  size: 16,
                  color: allUsersHaveInstalled
                      ? Colors.green
                      : installedUsers.isNotEmpty
                          ? Colors.orange
                          : Colors.grey,
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    installedUsers.isEmpty
                        ? 'Not installed'
                        : allUsersHaveInstalled
                            ? 'Installed by all users'
                            : 'Installed by: ${installedUsers.join(', ')}',
                    style: TextStyle(
                      fontSize: 12,
                      color: installedUsers.isEmpty
                          ? Colors.grey
                          : allUsersHaveInstalled
                              ? Colors.green
                              : Colors.orange,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Game details
                if (game.comment != null) ...[
                  const Text(
                    'Comment:',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  Text(game.comment!),
                  const SizedBox(height: 8),
                ],
                
                // Technical details
                Text(
                  'Technical Details:',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                Text('Release key: ${game.releaseKey}'),
                Text('IGDB key: ${game.igdbKey}'),
                Text('Slug: ${game.slug}'),
                
                const SizedBox(height: 8),
                
                // Ownership details
                const Text(
                  'Ownership:',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                ...selectedUserIds.map((userId) {
                  final user = users[userId];
                  if (user == null) return const SizedBox.shrink();
                  
                  final owns = game.owners.contains(userId);
                  final installed = game.installed.contains(userId);
                  
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      children: [
                        Icon(
                          owns ? Icons.check : Icons.close,
                          size: 16,
                          color: owns ? Colors.green : Colors.red,
                        ),
                        const SizedBox(width: 8),
                        Text(user.username),
                        if (owns) ...[
                          const Spacer(),
                          Icon(
                            installed ? Icons.download_done : Icons.download,
                            size: 16,
                            color: installed ? Colors.green : Colors.grey,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            installed ? 'Installed' : 'Not installed',
                            style: const TextStyle(fontSize: 12),
                          ),
                        ],
                      ],
                    ),
                  );
                }),
                
                // URL if available
                if (game.url != null) ...[
                  const SizedBox(height: 8),
                  TextButton.icon(
                    onPressed: () {
                      // In a real app, you would launch the URL
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('URL: ${game.url}')),
                      );
                    },
                    icon: const Icon(Icons.link),
                    label: const Text('View Game Info'),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}