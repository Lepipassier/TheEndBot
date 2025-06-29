import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from datetime import timedelta
import json
from keep_alive import keep_alive

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))
RULES_CHANNEL_ID = int(os.getenv('RULES_CHANNEL_ID'))
ACCEPT_ROLE_ID = int(os.getenv('ACCEPT_ROLE_ID'))

DATA_FILE = 'data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if "acceptance_number" not in data:
                    data["acceptance_number"] = 0
                    save_data(data)
                return data
            except json.JSONDecodeError:
                print(f"Erreur de décodage JSON dans {DATA_FILE}. Le fichier sera réinitialisé.")
                default_data = {"acceptance_number": 0}
                save_data(default_data)
                return default_data
    else:
        print(f"Fichier {DATA_FILE} non trouvé. Création avec les données par défaut.")
        default_data = {"acceptance_number": 0}
        save_data(default_data)
        return default_data

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

bot_data = load_data()
acceptance_number = bot_data["acceptance_number"]

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True
intents.presences = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} est connecté à Discord !')
    try:
        await bot.tree.sync()
        print("Tentative de synchronisation globale des commandes slash au démarrage.")
    except Exception as e:
        print(f"Erreur lors de la synchronisation des commandes slash au démarrage : {e}")

@bot.tree.command(name="sync", description="Synchronise les commandes slash du bot sur ce serveur.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def sync(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        await bot.tree.clear_commands(guild=interaction.guild)
        bot.tree.copy_global_to(guild=interaction.guild)
        synced = await bot.tree.sync(guild=interaction.guild)
        await interaction.followup.send(f"✅ Commandes slash synchronisées pour ce serveur ({len(synced)} commandes).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors de la synchronisation : {e}", ephemeral=True)

@bot.tree.command(name="mute", description="Mute un membre pour une durée et une raison.")
@discord.app_commands.describe(
    member="Le membre à mute.",
    time="La durée du mute (ex: 10m, 1h, 1d).",
    reason="La raison du mute."
)
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, time: str, reason: str):
    await interaction.response.defer(ephemeral=True)

    duration_seconds = 0
    try:
        if 'm' in time:
            duration_seconds = int(time.replace('m', '')) * 60
        elif 'h' in time:
            duration_seconds = int(time.replace('h', '')) * 3600
        elif 'd' in time:
            duration_seconds = int(time.replace('d', '')) * 86400
        else:
            await interaction.followup.send("Format de durée invalide. Utilise 'm' pour minutes, 'h' pour heures, 'd' pour jours (ex: 30m, 1h, 1d).")
            return

        if duration_seconds > 2419200:
            await interaction.followup.send("La durée du mute ne peut pas dépasser 28 jours.")
            return
            
    except ValueError:
        await interaction.followup.send("Durée invalide.")
        return

    try:
        await member.timeout(timedelta(seconds=duration_seconds), reason=reason)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🚫 Membre Muté",
                description=f"**{member.display_name}** a été muté.",
                color=discord.Color.red()
            )
            log_embed.add_field(name="Utilisateur", value=member.mention, inline=True)
            log_embed.add_field(name="Durée", value=time, inline=True)
            log_embed.add_field(name="Raison", value=reason, inline=False)
            log_embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
            log_embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
            log_embed.set_footer(text=f"Action effectuée par {interaction.user.name}")
            log_embed.timestamp = discord.utils.utcnow()
            await log_channel.send(embed=log_embed)
        
        await interaction.followup.send(f"✅ **{member.display_name}** a été muté pour {time} avec la raison : '{reason}'.", ephemeral=True)

    except discord.Forbidden:
        await interaction.followup.send("Je n'ai pas les permissions suffisantes pour mute ce membre. Assurez-vous que mon rôle est plus élevé que celui du membre.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Une erreur s'est produite lors du mute : {e}", ephemeral=True)

@bot.tree.command(name="unmute", description="Unmute un membre.")
@discord.app_commands.describe(
    member="Le membre à unmute."
)
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    if member.is_timed_out():
        try:
            await member.timeout(None, reason="Unmute par commande")

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title="🔓 Membre Unmute",
                    description=f"**{member.display_name}** a été unmute.",
                    color=discord.Color.blue()
                )
                log_embed.add_field(name="Utilisateur", value=member.mention, inline=True)
                log_embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
                log_embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
                log_embed.set_footer(text=f"Action effectuée par {interaction.user.name}")
                log_embed.timestamp = discord.utils.utcnow()
                await log_channel.send(embed=log_embed)
            
            await interaction.followup.send(f"✅ **{member.display_name}** a été unmute avec succès.", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("Je n'ai pas les permissions suffisantes pour unmute ce membre.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Une erreur s'est produite lors de l'unmute : {e}", ephemeral=True)
    else:
        await interaction.followup.send(f"**{member.display_name}** n'est pas mute.", ephemeral=True)

@bot.tree.command(name="advert", description="Envoie un avertissement en MP à un membre.")
@discord.app_commands.describe(
    member="Le membre à avertir.",
    reason="La raison de l'avertissement."
)
@discord.app_commands.checks.has_permissions(kick_members=True)
async def advert(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer(ephemeral=True)

    try:
        sender_name = interaction.user.display_name
        
        dm_embed = discord.Embed(
            title="⚠️ Avertissement Serveur ⚠️",
            description=f"Bonjour {member.display_name},\n\nTu as reçu un avertissement de la part de **{sender_name}** sur le serveur **{interaction.guild.name}**.",
            color=discord.Color.orange()
        )
        dm_embed.add_field(name="Raison de l'avertissement", value=reason, inline=False)
        dm_embed.set_footer(text="Merci de bien vouloir respecter les règles du serveur.")
        if interaction.guild and interaction.guild.icon:
            dm_embed.set_thumbnail(url=interaction.guild.icon.url)
        dm_embed.timestamp = discord.utils.utcnow()

        await member.send(embed=dm_embed)
        
        await interaction.followup.send(f"✅ Un avertissement discret a été envoyé en MP à **{member.display_name}** pour : **{reason}**.", ephemeral=True)

    except discord.Forbidden:
        await interaction.followup.send(f"Je n'ai pas pu envoyer de MP à **{member.display_name}**. Ils ont peut-être leurs MPs désactivés ou bloquent le bot.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Une erreur s'est produite lors de l'envoi de l'avertissement : {e}", ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.channel_id == RULES_CHANNEL_ID and str(payload.emoji) == '✅':
        guild = bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return

        role_to_add = guild.get_role(ACCEPT_ROLE_ID)
        if role_to_add is None:
            print(f"Le rôle avec l'ID {ACCEPT_ROLE_ID} n'a pas été trouvé. Veuillez vérifier le fichier .env.")
            return

        if role_to_add not in member.roles:
            try:
                await member.add_roles(role_to_add, reason="Acceptation des règles via réaction")
                
                global acceptance_number
                acceptance_number += 1
                bot_data["acceptance_number"] = acceptance_number
                save_data(bot_data)

                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    log_embed_rules = discord.Embed(
                        title="✅ Règles Acceptées",
                        description=f"**{member.display_name}** a accepté les règles du serveur.",
                        color=discord.Color.green()
                    )
                    log_embed_rules.add_field(name="Utilisateur", value=member.mention, inline=True)
                    log_embed_rules.add_field(name="Numéro d'acceptation", value=f"#{acceptance_number}", inline=True)
                    log_embed_rules.set_thumbnail(url=member.avatar.url if member.avatar else None)
                    log_embed_rules.set_footer(text=f"ID Utilisateur: {member.id}")
                    log_embed_rules.timestamp = discord.utils.utcnow()
                    await log_channel.send(embed=log_embed_rules)
                else:
                    print(f"Le salon de log général avec l'ID {LOG_CHANNEL_ID} n'a pas été trouvé.")
                    rules_channel = bot.get_channel(RULES_CHANNEL_ID)
                    if rules_channel:
                         await rules_channel.send(f"**{member.display_name}** a accepté les règles du serveur. #{acceptance_number}")


            except discord.Forbidden:
                print(f"Je n'ai pas les permissions d'ajouter le rôle {role_to_add.name} à {member.display_name}.")
            except Exception as e:
                print(f"Erreur lors de l'ajout du rôle ou de l'envoi du message pour {member.display_name}: {e}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message(f"Tu n'as pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
    elif isinstance(error, discord.app_commands.BotMissingPermissions):
        await interaction.response.send_message(f"Il me manque : {', '.join(error.missing_permissions)}", ephemeral=True)
    else:
        await interaction.response.send_message(f"Une erreur inattendue s'est produite : {error}", ephemeral=True)

keep_alive()
bot.run(TOKEN)