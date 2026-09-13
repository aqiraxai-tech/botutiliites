import os
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Cargar variables de entorno (para entorno local)
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# --- CONFIGURACIÓN E INTENTOS ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Bases de datos simples en memoria
user_warns = {}
active_giveaways = {}


# --- EVENTO ON_READY (Status, Custom Status, AutoMod) ---
@bot.event
async def on_ready():
    # Status: No molestar + Jugando: El Futuro Es Hoy.
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name="El Futuro Es Hoy."
    )
    await bot.change_presence(status=discord.Status.dnd, activity=activity)
    
    try:
        synced = await bot.tree.sync()
        print(f"🤖 Bot activo como {bot.user} | {len(synced)} comandos sincronizados.")
    except Exception as e:
        print(f"❌ Error sincronizando comandos: {e}")

    # Configurar AutoMod en los servidores donde está presente
    for guild in bot.guilds:
        await setup_automod(guild)


async def setup_automod(guild: discord.Guild):
    """Crea la regla de AutoMod para bloquear enlaces restringidos."""
    try:
        if not guild.me.guild_permissions.manage_guild:
            return

        rule_name = "Aqirax Protection - Link Filter"
        existing_rules = await guild.fetch_automod_rules()
        
        if any(rule.name == rule_name for rule in existing_rules):
            return

        blocked_keywords = [
            "*discord.gg*",
            "*discord.com*",
            "*youtube.com*"
        ]

        await guild.create_automod_rule(
            name=rule_name,
            event_type=discord.AutoModRuleEventType.message_send,
            trigger_type=discord.AutoModRuleTriggerType.keyword,
            trigger_metadata=discord.AutoModTriggerMetadata(keyword_filter=blocked_keywords),
            actions=[discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message)],
            enabled=True,
            reason="Filtro automático de Aqirax AI"
        )
        print(f"✅ AutoMod activo en: {guild.name}")
    except Exception as e:
        print(f"⚠️ Error al crear AutoMod en {guild.name}: {e}")


# --- COMANDOS GENERALES Y DE MODERACIÓN ---

@bot.tree.command(name="help", description="Lista de comandos del bot.")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Comandos de Aqirax Bot",
        description="¡El futuro es hoy, mano! Aquí tienes el panel de control:",
        color=discord.Color.blue()
    )
    embed.add_field(name="🛡️ Moderación", value="`/ban` `/kick` `/warn` `/clearwarns`", inline=False)
    embed.add_field(name="ℹ️ Información", value="`/user-info` `/server-info` `/channel-info` `/banner`", inline=False)
    embed.add_field(name="🎨 Utilidades & Sorteos", value="`/send-embed` `/giveaway`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="ban", description="Banea a un miembro del servidor.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón especificada"):
    await usuario.ban(reason=razon)
    await interaction.response.send_message(f"💥 **{usuario}** fue baneado del servidor. Razón: {razon}")


@bot.tree.command(name="kick", description="Expulsa a un miembro del servidor.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón especificada"):
    await usuario.kick(reason=razon)
    await interaction.response.send_message(f"🚪 **{usuario}** fue expulsado. Razón: {razon}")


@bot.tree.command(name="warn", description="Añade una advertencia a un usuario.")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón especificada"):
    uid = usuario.id
    user_warns[uid] = user_warns.get(uid, 0) + 1
    await interaction.response.send_message(f"⚠️ **{usuario.mention}** ha sido advertido. Total de advertencias: **{user_warns[uid]}**. Razón: {razon}")


@bot.tree.command(name="clearwarns", description="Limpia el historial de advertencias de un usuario.")
@app_commands.checks.has_permissions(manage_messages=True)
async def clearwarns(interaction: discord.Interaction, usuario: discord.Member):
    user_warns[usuario.id] = 0
    await interaction.response.send_message(f"🧹 Historial de advertencias reseteado para **{usuario.mention}**.")


@bot.tree.command(name="user-info", description="Información detallada de un usuario.")
async def user_info(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    embed = discord.Embed(title=f"👤 Perfil de {target.name}", color=discord.Color.green())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=target.id, inline=True)
    embed.add_field(name="Ingreso al servidor", value=target.joined_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Cuenta creada", value=target.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Warns", value=user_warns.get(target.id, 0), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="server-info", description="Información general del servidor.")
async def server_info(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=f"🏰 Servidor: {g.name}", color=discord.Color.purple())
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="Miembros", value=g.member_count, inline=True)
    embed.add_field(name="Creador", value=g.owner, inline=True)
    embed.add_field(name="Creación", value=g.created_at.strftime("%d/%m/%Y"), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="channel-info", description="Información del canal actual.")
async def channel_info(interaction: discord.Interaction):
    c = interaction.channel
    embed = discord.Embed(title=f"📺 Canal: #{c.name}", color=discord.Color.teal())
    embed.add_field(name="ID", value=c.id, inline=True)
    embed.add_field(name="Categoría", value=c.category.name if c.category else "Sin categoría", inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="banner", description="Muestra el banner de perfil de un usuario.")
async def banner(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    user_fetched = await bot.fetch_user(target.id)
    if user_fetched.banner:
        embed = discord.Embed(title=f"🖼️ Banner de {target.name}", color=discord.Color.dark_theme())
        embed.set_image(url=user_fetched.banner.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"❌ {target.name} no tiene un banner personalizado.", ephemeral=True)


# --- CREADOR DE EMBEDS CON INTERFAZ ---

class EmbedBuilderModal(discord.ui.Modal, title="🛠️ Creador de Embeds"):
    title_input = discord.ui.TextInput(label="Título", placeholder="Título del mensaje...", required=True)
    desc_input = discord.ui.TextInput(label="Descripción", style=discord.TextStyle.paragraph, placeholder="Contenido...", required=True)
    color_input = discord.ui.TextInput(label="Color Hex (ej: #FF0000)", placeholder="#3498db", required=False, max_length=7)

    async def on_submit(self, interaction: discord.Interaction):
        hex_val = self.color_input.value or "#3498db"
        try:
            color = int(hex_val.lstrip('#'), 16)
        except ValueError:
            color = 0x3498db

        embed = discord.Embed(
            title=self.title_input.value,
            description=self.desc_input.value,
            color=color
        )

        view = EmbedPreviewView(embed)
        await interaction.response.send_message(
            content="👀 **Vista previa (solo visible para ti):**",
            embed=embed,
            view=view,
            ephemeral=True
        )


class EmbedPreviewView(discord.ui.View):
    def __init__(self, embed: discord.Embed):
        super().__init__(timeout=None)
        self.embed = embed

    @discord.ui.button(label="🚀 Enviar al canal", style=discord.ButtonStyle.green)
    async def send_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.send(embed=self.embed)
        await interaction.response.send_message("✅ ¡Embed publicado con éxito!", ephemeral=True)

    @discord.ui.button(label="✏️ Seguir Editando", style=discord.ButtonStyle.blurple)
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EmbedBuilderModal()
        modal.title_input.default = self.embed.title
        modal.desc_input.default = self.embed.description
        await interaction.response.send_modal(modal)


@bot.tree.command(name="send-embed", description="Abre el editor visual para construir un Embed.")
async def send_embed(interaction: discord.Interaction):
    await interaction.response.send_modal(EmbedBuilderModal())


# --- SISTEMA DE SORTEOS / GIVEAWAYS ---

class GiveawayModal(discord.ui.Modal, title="🎉 Configurar Giveaway"):
    prize = discord.ui.TextInput(label="Premio / Título", placeholder="Ej: Discord Nitro 1 Mes", required=True)
    duration = discord.ui.TextInput(label="Duración en minutos", placeholder="Ej: 10", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = float(self.duration.value)
        except ValueError:
            await interaction.response.send_message("❌ Ingresa una duración numérica válida.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎉 ¡SORTEO: {self.prize.value}! 🎉",
            description=f"¡Haz clic abajo para participar!\n\n⏳ **Duración:** {minutes} minuto(s)\n👤 **Organizador:** {interaction.user.mention}",
            color=discord.Color.gold()
        )

        view = GiveawayView()
        await interaction.response.send_message("¡Sorteo creado exitosamente!", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        active_giveaways[msg.id] = {
            "participants": set(),
            "prize": self.prize.value
        }

        await asyncio.sleep(minutes * 60)
        await end_giveaway(msg, self.prize.value)


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎁 Entrar al Sorteo", style=discord.ButtonStyle.primary, custom_id="claim_giveaway_btn")
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = interaction.message.id
        if msg_id not in active_giveaways:
            await interaction.response.send_message("❌ Este sorteo ya ha finalizado.", ephemeral=True)
            return

        participants = active_giveaways[msg_id]["participants"]
        user_id = interaction.user.id

        if user_id in participants:
            await interaction.response.send_message("⚠️ Ya estás participando en este sorteo.", ephemeral=True)
        else:
            participants.add(user_id)
            await interaction.response.send_message("✅ ¡Entraste al sorteo correctamente! 🍀", ephemeral=True)


async def end_giveaway(message: discord.Message, prize: str):
    data = active_giveaways.pop(message.id, None)
    if not data:
        return

    participants = list(data["participants"])

    if not participants:
        embed = discord.Embed(
            title=f"🎉 SORTEO FINALIZADO: {prize}",
            description="❌ El tiempo terminó y no hubo participantes.",
            color=discord.Color.red()
        )
        await message.edit(embed=embed, view=None)
        return

    winner_id = random.choice(participants)
    winner = message.guild.get_member(winner_id)

    embed = discord.Embed(
        title=f"🎉 SORTEO FINALIZADO: {prize}",
        description=f"🏆 **Ganador:** {winner.mention if winner else 'Usuario desvinculado'}\n👥 **Total de Participantes:** {len(participants)}",
        color=discord.Color.green()
    )
    await message.edit(embed=embed, view=None)
    await message.channel.send(f"🎊 ¡Felicidades {winner.mention}! Has ganado **{prize}** 🔥")


@bot.tree.command(name="giveaway", description="Inicia un nuevo sorteo.")
@app_commands.checks.has_permissions(manage_events=True)
async def giveaway(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayModal())


# --- EJECUCIÓN ---
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("❌ No se encontró la variable DISCORD_TOKEN.")
    bot.run(TOKEN)
