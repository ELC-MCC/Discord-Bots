import discord
import os
import re
import bot_config

class RoleBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        
        # Set nickname
        for guild in self.guilds:
            try:
                await guild.me.edit(nick=bot_config.ROLE_BOT_NICKNAME)
                print(f"Changed nickname to '{bot_config.ROLE_BOT_NICKNAME}' in {guild.name}")
            except Exception as e:
                print(f"Nickname change failed in {guild.name}: {e}")

    async def on_message(self, message):
        # Ignore own messages
        if message.author == self.user:
            return

        # Universal Admin Setup
        if message.content.startswith('!admin_setup'):
             if not message.author.guild_permissions.administrator:
                 return

             # Check configured admin channel
             admin_channel_id = os.getenv('ADMIN_CHANNEL_ID')
             if admin_channel_id and str(message.channel.id) != str(admin_channel_id):
                return

             # Wait for purge
             import asyncio
             await asyncio.sleep(2)

             embed = discord.Embed(
                 title="Sudo Master (Role Bot)",
                 description="Manages roles and verification.\n\n**Commands:**\n`!setup_reaction #channel \"Title\" <Emoji> @Role ...`\n*(Creates a self-assign role menu)*\n\n`!fix_roles @OldRole @Pre2024Role @Post2024Role`\n*(Migrates users based on join date)*",
                 color=0x3498DB
             )
             await message.channel.send(embed=embed)
             return

        # Debug: Print raw message content
        print(f"DEBUG: Message from {message.author}: {message.content}")

        # Command: !setup_reaction <#channel> "Title" <Emoji> @Role ...
        if message.content.startswith('!setup_reaction'):
            # Check Perms
            if not message.channel.permissions_for(message.author).administrator:
                await message.reply("`sudo` access denied.")
                return

            try:
                # 1. Extract Target Channel
                if not message.channel_mentions:
                    await message.reply("Target channel not found.")
                    return
                target_channel = message.channel_mentions[0]

                # 2. Extract Title
                title = "React to get Roles!"
                quote_match = re.search(r'"([^"]*)"', message.content)
                if quote_match:
                    title = quote_match.group(1)

                # 3. Clean content for parsing pairs
                # Remove command, channel mention, and title to avoid false matches
                clean_content = message.content.replace('!setup_reaction', '', 1)
                clean_content = clean_content.replace(target_channel.mention, '', 1)
                if quote_match:
                    clean_content = clean_content.replace(quote_match.group(0), '', 1)
                
                # 4. Find Emoji-Role Pairs
                # Regex looks for: (Non-whitespace) followed by (Role Mention)
                # Matches: "🔴 <@&123>" or "<:custom:123> <@&456>"
                pair_pattern = r'(\S+)\s+(<@&\d+>)'
                matches = re.findall(pair_pattern, clean_content)

                if not matches:
                    await message.reply('Usage: `!setup_reaction #channel "Title" <Emoji> @Role ...`\nExample: `!setup_reaction #gen "Roles" 🔴 @Red 🔵 @Blue`')
                    return

                # 5. Build Description and Role Map
                description = ""
                emojis_to_add = []
                
                for emoji, role_mention in matches:
                    description += f"{emoji} : {role_mention}\n"
                    emojis_to_add.append(emoji)
                
                # 6. Create and Send Embed
                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=0x3498DB # Blue for info
                )
                embed.set_footer(text=bot_config.ROLE_BOT_FOOTER)

                sent_msg = await target_channel.send(embed=embed)
                
                # 7. Add Reactions
                for emoji in emojis_to_add:
                    try:
                        await sent_msg.add_reaction(emoji)
                    except Exception as e:
                        print(f"Failed to add reaction {emoji}: {e}")
                        # Continue adding others even if one fails
                
                await message.reply(f"Reaction Role message created in {target_channel.mention}")

            except Exception as e:
                await message.reply(f"Error: {e}")
                print(f"Error in setup_reaction: {e}")

        # Command: !fix_roles <remove_role_id> <pre_may_role_id> <post_may_role_id>
        if message.content.startswith('!fix_roles'):
            await self.chat_command_fix_roles(message)

    async def on_raw_reaction_add(self, payload):
        await self.handle_reaction(payload, add=True)

    async def on_raw_reaction_remove(self, payload):
        await self.handle_reaction(payload, add=False)

    async def handle_reaction(self, payload, add):
        # Ignore bots and self
        if payload.user_id == self.user.id:
            return

        # Fetch Guild
        guild = self.get_guild(payload.guild_id)
        if not guild:
            return
        
        # Fetch Member (for removal events, 'member' might be None in payload, need to fetch)
        member = guild.get_member(payload.user_id)
        if not member:
            return # Member left?

        # Fetch Channel and Message
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return 
        
        # Check Author (Must be ME)
        if message.author.id != self.user.id:
            return

        # Check Embeds
        if not message.embeds:
            return
        
        embed = message.embeds[0]
        
        # Check Footer (to distinguish from other Sudo Master messages if needed)
        # We check if the footer matches what we expect, OR contains our bot name if it was partial match previously.
        # But stricter is better: match config.
        # However, to support old messages, we might want to keep "Sudo Master" check or be flexible.
        # For now, let's use the config value check.
        # But wait, old messages have "Sudo Master". If I change config, old messages might stop working if I enforce exact match.
        # The prompt says "change all the public facing names", implying a rebrand.
        # If I change the check to `bot_config.ROLE_BOT_FOOTER`, then old messages with "Sudo Master" won't work if the user changes the footer.
        # But that might be desired behavior (only manage my new messages).
        # OR I should check if the footer contains the *current* configured name OR "Sudo Master" (legacy)?
        # The user said "these are critical info", implying they want to control it.
        # I'll stick to using the config variable for the check. If they change it, they might expect old ones to be ignored or they will update them.
        # Actually, let's just check if footer exists. The logic relies on `embed.description` parsing mainly.
        # The footer check is a safeguard.
        # I will use `bot_config.ROLE_BOT_FOOTER` in the check.
        
        if not embed.footer or (bot_config.ROLE_BOT_FOOTER not in (embed.footer.text or "") and "Sudo Master" not in (embed.footer.text or "")):
             # I'll keep "Sudo Master" as a legacy fallback for now to not break existing reaction roles during migration, 
             # unless user explicitly changes it to something else that conflicts.
             # Actually, simpler is:
             pass
        
        # Let's just use the config.
        if not embed.footer or bot_config.ROLE_BOT_FOOTER not in (embed.footer.text or ""):
             # Fallback for legacy support if needed, but let's stick to the prompt.
             # If I strictly enforce new footer, old messages break.
             # I will allow "Sudo Master" hardcoded fallback for now to be safe, or just relying on description format?
             # Description format is specific enough.
             pass

        # Re-reading the code:
        # It checks: `if not embed.footer or "Sudo Master" not in (embed.footer.text or ""):`
        # I will change it to check for the configured name.
        
        if not embed.footer or bot_config.ROLE_BOT_FOOTER not in (embed.footer.text or ""):
            # OPTIONAL: Allow legacy "Sudo Master"
            if "Sudo Master" not in (embed.footer.text or ""):
                return

        # LOGIC: Read the Embed Description to find the matching role
        # ... (rest of logic)
        
        emoji_str = str(payload.emoji) 
        
        description_lines = (embed.description or "").split('\n')
        target_role_id = None

        for line in description_lines:
            if line.strip().startswith(emoji_str):
                role_match = re.search(r'<@&(\d+)>', line)
                if role_match:
                    target_role_id = int(role_match.group(1))
                    break
        
        if target_role_id:
            role = guild.get_role(target_role_id)
            if role:
                try:
                    if add:
                        await member.add_roles(role)
                        print(f"Added role {role.name} to {member.name}")
                    else:
                        await member.remove_roles(role)
                        print(f"Removed role {role.name} from {member.name}")
                except discord.Forbidden:
                    print(f"Error: Missing permissions to manage roles (Target Role: {role.name}).")
            else:
                print(f"Error: Role ID {target_role_id} not found in guild.")

    async def on_member_join(self, member):
        """Automatically assign a role when a new member joins."""
        if member.pending:
            print(f"RoleBot: {member.name} is pending verification. Waiting...")
            return

        await self.assign_auto_role(member)

    async def on_member_update(self, before, after):
        """Handle member update events, specifically regarding verification."""
        # Check if member completed verification (pending: True -> False)
        if before.pending and not after.pending:
            print(f"RoleBot: {after.name} completed verification.")
            await self.assign_auto_role(after)

    async def assign_auto_role(self, member):
        if bot_config.AUTO_JOIN_ROLE_ID:
            role = member.guild.get_role(bot_config.AUTO_JOIN_ROLE_ID)
            if role:
                try:
                    await member.add_roles(role)
                    print(f"Auto-assigned role {role.name} to {member.name}")
                except Exception as e:
                    print(f"Failed to auto-assign role to {member.name}: {e}")
            else:
                print(f"Auto-join role ID {bot_config.AUTO_JOIN_ROLE_ID} not found.")

    async def chat_command_fix_roles(self, message):
         # Command: !fix_roles <remove_role_id> <pre_may_role_id> <post_may_role_id>
        if not message.author.guild_permissions.administrator:
            await message.reply("Administrator permissions required.")
            return

        parts = message.content.split()
        if len(parts) != 4:
            await message.reply("Usage: `!fix_roles <exclude_role_id> <pre_may_role_id> <post_may_role_id>`")
            return

        if len(message.role_mentions) == 3:
            # Use mentions if exactly 3 are provided
            remove_role_id = message.role_mentions[0].id
            pre_may_role_id = message.role_mentions[1].id
            post_may_role_id = message.role_mentions[2].id
        else:
            try:
                # Clean inputs to handle raw IDs (123) or Mentions (<@&123>) if manual ID entry
                remove_role_id = int(re.sub(r'\D', '', parts[1]))
                pre_may_role_id = int(re.sub(r'\D', '', parts[2]))
                post_may_role_id = int(re.sub(r'\D', '', parts[3]))
            except ValueError:
                await message.reply("Invalid arguments. Please Mention the 3 roles or provide their IDs.")
                return

        guild = message.guild
        remove_role = guild.get_role(remove_role_id)
        pre_may_role = guild.get_role(pre_may_role_id)
        post_may_role = guild.get_role(post_may_role_id)

        if not pre_may_role or not post_may_role:
             await message.reply("One or more target roles not found.")
             return
        
        if not remove_role:
            await message.reply(f"Role to remove (ID: {remove_role_id}) not found in this guild.")
            return

        # Date Threshold: May 1st, 2024
        from datetime import datetime, timezone
        cutoff_date = datetime(2024, 5, 1, tzinfo=timezone.utc)
        
        count_removed = 0
        count_pre = 0
        count_post = 0
        
        # Pre-calculation
        target_members = [m for m in guild.members if remove_role in m.roles]
        
        status_msg = await message.reply(
            f"**Starting Migration**\n"
            f"Total Members: {len(guild.members)}\n"
            f"Members with Role '{remove_role.name}': {len(target_members)}\n"
            f"Processing..."
        )
        
        processed_count = 0

        for member in guild.members:
            processed_count += 1
            if processed_count % 25 == 0:
                try:
                    await status_msg.edit(content=f"Processing... {processed_count}/{len(guild.members)} members checked.")
                except:
                    pass

            # Check if they have the role to be removed/swapped
            # The user said: "remove a role and give people another role... based on whether or not the account joined prior to may 2024"
            # It implies we only act on people who *have* the role to be removed? 
            # OR does it mean "for everyone, ensure they have the right role"?
            # "allow an admin to remove a role and give people another role automatically"
            # I will assume we only process members who HAVE the `remove_role_id`. 
            # If `remove_role_id` is 0 or something, maybe they want to check everyone? 
            # I'll stick to acting on members who have the role to be removed, as implied by "remove a role".
            
            member_role_ids = [r.id for r in member.roles]
            
            if remove_role_id in member_role_ids:
                try:
                    # Remove old role
                    if remove_role:
                        await member.remove_roles(remove_role)
                        count_removed += 1
                    
                    # Add new role based on join date
                    if member.joined_at < cutoff_date:
                        await member.add_roles(pre_may_role)
                        count_pre += 1
                    else:
                        await member.add_roles(post_may_role)
                        count_post += 1
                        
                except Exception as e:
                    print(f"Error processing {member.name}: {e}")
        
        await status_msg.edit(content=f"**Role Migration Complete**\n"
                                      f"Checked {len(guild.members)} members.\n"
                                      f"Removed Old Role from: {count_removed} members\n"
                                      f"Assigned Pre-May Role: {count_pre}\n"
                                      f"Assigned Post-May Role: {count_post}")

