import discord
import os
import re
import bot_config
from datetime import datetime, timezone

class MigrationModal(discord.ui.Modal, title="Migrate Alumni Roles"):
    alumni_role_id = discord.ui.TextInput(label="Alumni Role ID", placeholder="123456789", required=True)
    member_role_id = discord.ui.TextInput(label="Member Role ID", placeholder="987654321", required=True)
    cutoff_date = discord.ui.TextInput(label="Cutoff Date (YYYY-MM-DD)", placeholder="2024-05-01", default="2024-05-01", required=True)

    def __init__(self, bot, channel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ Starting Migration... checks logs/channel.", ephemeral=True)
        
        try:
            guild = interaction.guild
            alumni_role = guild.get_role(int(self.alumni_role_id.value))
            member_role = guild.get_role(int(self.member_role_id.value))
            
            date_str = self.cutoff_date.value
            cutoff_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            
            if not alumni_role or not member_role:
                 await self.channel.send("❌ Error: Invalid Role IDs provided in Modal.")
                 return

            # Call the helper logic
            await self.bot._perform_migration(self.channel, guild, alumni_role, member_role, cutoff_dt)
            
        except ValueError:
            await self.channel.send("❌ Error: Invalid Date Format. Use YYYY-MM-DD.")
        except Exception as e:
            await self.channel.send(f"❌ Error starting migration: {e}")

class AdminDashboardView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Migrate Roles", style=discord.ButtonStyle.primary, emoji="🔄")
    async def migrate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Open Modal
        await interaction.response.send_modal(MigrationModal(self.bot, interaction.channel))


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
                 description="Manages roles and verification.\n\n**Commands:**\n`!setup_reaction #channel \"Title\" <Emoji> @Role ...`\n*(Creates a self-assign role menu)*\n\n**Migration:**\nClick the button below to migrate users based on join date.",
                 color=0x3498DB
             )
             view = AdminDashboardView(self)
             await message.channel.send(embed=embed, view=view)
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



        # Command: !migrate_alumni @Alumni @Member [Optional:@OldMsg]
        if message.content.startswith('!migrate_alumni'):
             print(f"DEBUG: RoleBot received !migrate_alumni command from {message.author}")
             try:
                 await self.chat_command_migrate_alumni(message)
             except Exception as e:
                 print(f"CRITICAL ERROR in !migrate_alumni dispatch: {e}")
                 import traceback
                 traceback.print_exc()
                 await message.reply(f"❌ Critical Error: {e}")

    async def chat_command_migrate_alumni(self, message):
        """
        Migrates users to Alumni or Member roles based on join date.
        Cutoff: May 1st, 2024
        Usage: !migrate_alumni @AlumniRole @MemberRole [Optional:@OldRoleToRemove]
        """
        # 1. Permission Check
        if not message.author.guild_permissions.administrator:
            await message.reply("Administrator permissions required.")
            return

        # 2. Parse Arguments using Regex (message.role_mentions is unreliable for order)
        import re
        # Find all role mentions in order: <@&123456789>
        role_matches = re.findall(r'<@&(\d+)>', message.content)

        if len(role_matches) < 2:
            await message.reply("Usage: `!migrate_alumni @AlumniRole @OngoingMemberRole [Optional:@OldRoleToRemove]`")
            return

        guild = message.guild
        
        # 1. First Match -> Alumni Role (Strict Order)
        alumni_role = guild.get_role(int(role_matches[0]))
        # 2. Second Match -> Member Role (Strict Order)
        member_role = guild.get_role(int(role_matches[1]))
        
        # 3. Third Match -> Old Role (Optional)
        remove_role = None
        if len(role_matches) > 2:
            remove_role = guild.get_role(int(role_matches[2]))

        if not alumni_role or not member_role:
             await message.reply("❌ Error: Could not resolve one of the roles. Please check the IDs.")
             return
        
        from datetime import datetime, timezone
        
        # Check for Date: YYYY-MM-DD
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', message.content)
        if date_match:
             try:
                 cutoff_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                 print(f"DEBUG: Using Custom Date: {cutoff_date}")
             except ValueError:
                 await message.reply("❌ Error: Invalid date format. Use YYYY-MM-DD.")
                 return
        else:
             # Default Cutoff Date: May 1st, 2024 (UTC)
             cutoff_date = datetime(2024, 5, 1, tzinfo=timezone.utc)

        # 4. START MIGRATION HELPER
        await self._perform_migration(message.channel, guild, alumni_role, member_role, cutoff_date, remove_role)

    async def _perform_migration(self, channel, guild, alumni_role, member_role, cutoff_date, remove_role=None):
        """
        Reusable migration logic for both Chat Command and Admin UI.
        """
        stats = {
            "processed": 0,
            "alumni_added": 0,
            "members_added": 0,
            "roles_removed": 0,
            "errors": 0
        }

        # Notify Start
        status_msg = await channel.send(
            f"**Starting Migration**\n"
            f"Cutoff Date: {cutoff_date.strftime('%Y-%m-%d')}\n"
            f"Alumni Role: {alumni_role.mention}\n"
            f"Member Role: {member_role.mention}\n"
            f"Remove Role: {remove_role.mention if remove_role else 'None'}\n"
            f"Total Members to Check: {len(guild.members)}\n"
            f"Processing..."
        )

        try:
            # Iterate Members
            for member in guild.members:
                if member.bot: 
                    continue # Skip bots
                
                stats["processed"] += 1
                
                # Update status message every 50 members to avoid rate limits
                if stats["processed"] % 50 == 0:
                    try:
                        await status_msg.edit(content=f"Processing... {stats['processed']}/{len(guild.members)} members checked...")
                    except: 
                        pass # Ignore editing errors

                try:
                    # Determine Status based on Join Date
                    if not member.joined_at:
                        print(f"Skipping {member.name}: No joined_at date.")
                        continue

                    is_alumni = member.joined_at < cutoff_date
                    
                    import asyncio
                    
                    if is_alumni:
                        # 1. Give Alumni Role if they don't have it
                        if alumni_role not in member.roles:
                            await member.add_roles(alumni_role)
                            stats["alumni_added"] += 1
                            print(f"[Migration] {member.name} -> Added Alumni")
                            await asyncio.sleep(1) 
                        
                        # 2. REMOVE Member Role if they have it (Strict Separation)
                        if member_role in member.roles:
                            await member.remove_roles(member_role)
                            stats["roles_removed"] += 1
                            print(f"[Migration] {member.name} -> Removed Member (Should be Alumni)")
                            await asyncio.sleep(1)

                    else:
                        # 1. Give Member Role if they don't have it
                        if member_role not in member.roles:
                            await member.add_roles(member_role)
                            stats["members_added"] += 1
                            print(f"[Migration] {member.name} -> Added Member")
                            await asyncio.sleep(1)
                        
                        # 2. REMOVE Alumni Role if they have it (Strict Separation)
                        if alumni_role in member.roles:
                            await member.remove_roles(alumni_role)
                            stats["roles_removed"] += 1
                            print(f"[Migration] {member.name} -> Removed Alumni (Should be Member)")
                            await asyncio.sleep(1)

                    # ACTION 2: Remove Old Role (if specified and present)
                    if remove_role and remove_role in member.roles:
                        await member.remove_roles(remove_role)
                        stats["roles_removed"] += 1
                        await asyncio.sleep(0.5) # Rate limit protection
                
                except discord.Forbidden:
                    print(f"ERROR: Missing permissions to manage roles for {member.name}.")
                    stats["errors"] += 1
                except Exception as e:
                    print(f"ERROR processing {member.name}: {e}")
                    stats["errors"] += 1
                
                # Small sleep between every user just to be safe
                import asyncio
                await asyncio.sleep(0.1)
            
            # Final Report
            await status_msg.edit(content=(
                f"**Migration Complete** ✅\n"
                f"-------------------------\n"
                f"**Total Processed:** {stats['processed']}\n"
                f"**Alumni Roles Added:** {stats['alumni_added']}\n"
                f"**Member Roles Added:** {stats['members_added']}\n"
                f"**Old Roles Removed:** {stats['roles_removed']}\n"
                f"**Errors:** {stats['errors']}\n"
                f"-------------------------\n"
                f"Cutoff was: {cutoff_date.strftime('%Y-%m-%d')}"
            ))

        except Exception as e:
            await status_msg.edit(content=f"**CRITICAL ERROR during migration:** {e}")
            import traceback
            traceback.print_exc()

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
        print(f"DEBUG: RoleBot.on_member_join triggered for {member.name} (ID: {member.id})")
        print(f"DEBUG: Member Pending Status: {member.pending}")
        
        if member.pending:
            print(f"RoleBot: {member.name} is pending verification. Waiting...")
            return

        print(f"RoleBot: {member.name} is NOT pending. Assigning role...")
        await self.assign_auto_role(member)

    async def on_member_update(self, before, after):
        """Handle member update events, specifically regarding verification."""
        # Log state changes for debugging
        if before.pending != after.pending:
            print(f"DEBUG: RoleBot.on_member_update: {after.name} Pending changed: {before.pending} -> {after.pending}")

        # Check if member completed verification (pending: True -> False)
        if before.pending and not after.pending:
            print(f"RoleBot: {after.name} completed verification.")
            await self.assign_auto_role(after)

    async def assign_auto_role(self, member):
        print(f"DEBUG: assign_auto_role ENTERED for {member.name}")
        try:
            role_id = bot_config.AUTO_JOIN_ROLE_ID
            
            # Fallback to .env MEMBER_ROLE_ID if config is 0
            if not role_id:
                 env_role_id = os.getenv('MEMBER_ROLE_ID')
                 if env_role_id:
                     try:
                         role_id = int(env_role_id)
                         print(f"DEBUG: Using MEMBER_ROLE_ID from .env: {role_id}")
                     except ValueError:
                         print(f"ERROR: MEMBER_ROLE_ID in .env is not a valid integer: {env_role_id}")
    
            print(f"DEBUG: assign_auto_role processing for {member.name}. Final Role ID: {role_id}")
            
            if not role_id:
                print("DEBUG: AUTO_JOIN_ROLE_ID is not set (None or 0). Skpping.")
                return
    
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                    print(f"Auto-assigned role {role.name} to {member.name}")
                except discord.Forbidden:
                    print(f"ERROR: Missing Permissions to assign role {role.name}. Check Bot Role Position!")
                except Exception as e:
                    print(f"ERROR: Failed to auto-assign role to {member.name}: {e}")
            else:
                print(f"ERROR: Auto-join role ID {role_id} not found in guild {member.guild.name}.")
                # List available roles for debug
                roles = [f"{r.name}:{r.id}" for r in member.guild.roles]
                print(f"DEBUG: Available Roles: {', '.join(roles)}")
        except Exception as e:
            print(f"CRITICAL ERROR in assign_auto_role: {e}")
            import traceback
            traceback.print_exc()



